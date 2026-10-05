"""Verify an existing deployment; never deploy or broadcast a transaction.

Fill in the constants below with the actual deployment addresses and the
ORIGINAL constructor treasury (not a subsequently updated treasury).
Run: mox run verify --network monad-testnet (or --network monad).
Only the explorer API credential comes from moccasin.toml / .env.
"""

import boa
from boa.explorer import Etherscan
from boa.util.abi import Address, abi_encode
from moccasin.config import get_active_network

from src import payday_factory, payday_goal

# Replace these after deployment. No address is read from env or CLI arguments.
# FACTORY_ADDRESS is also read by script/verify_goals.py.
FACTORY_ADDRESS = "0x0000000000000000000000000000000000000000"
GOAL_BLUEPRINT_ADDRESS = "0x0000000000000000000000000000000000000000"
ORIGINAL_TREASURY_ADDRESS = "0x0000000000000000000000000000000000000000"
URI_CREATED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_IN_PROGRESS = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_COMPLETED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"


def deployment_addresses():
    addresses = tuple(
        Address(value)
        for value in (
            FACTORY_ADDRESS,
            GOAL_BLUEPRINT_ADDRESS,
            ORIGINAL_TREASURY_ADDRESS,
        )
    )
    if any(int(address, 16) == 0 for address in addresses):
        raise ValueError(
            "Fill in the three hardcoded deployment addresses in script/verify.py."
        )
    return addresses


def moccasin_main():
    factory_address, blueprint_address, treasury_address = deployment_addresses()
    network = get_active_network()
    if network.chain_id not in (143, 10143) or network.is_local_or_forked_network():
        raise ValueError("Select the live monad or monad-testnet network.")
    if not network.explorer_api_key or network.explorer_api_key.startswith("$"):
        raise ValueError("Set ETHERSCAN_API_KEY for the configured explorer.")
    if not boa.env.get_code(factory_address):
        raise ValueError("No factory code at the hardcoded address on this network.")

    factory = payday_factory.at(factory_address)
    if factory.GOAL_BLUEPRINT() != blueprint_address:
        raise ValueError("Factory blueprint does not match GOAL_BLUEPRINT_ADDRESS.")
    expected_blueprint = b"\xfe\x71\x00" + payday_goal.compiler_data.bytecode
    if boa.env.get_code(blueprint_address) != expected_blueprint:
        raise ValueError(
            "Deployed blueprint does not match the local compiler/source build."
        )
    factory.ctor_calldata = abi_encode(
        "(address,address,string,string,string)",
        (
            blueprint_address,
            treasury_address,
            URI_CREATED,
            URI_IN_PROGRESS,
            URI_COMPLETED,
        ),
    )
    # Moccasin 0.4.4's wrapper constructs Etherscan without its chain_id, which
    # defaults to Ethereum mainnet. Use the same Titanoboa backend explicitly.
    verifier = Etherscan(
        uri=network.explorer_uri,
        api_key=network.explorer_api_key,
        chain_id=network.chain_id,
    )
    result = boa.verify(factory, verifier)
    result.wait_for_verification()
    print(f"Factory verified: {factory_address}")
    print(f"Blueprint bytecode matched locally: {blueprint_address}")
    print("EIP-5202 blueprint explorer verification is not supported by this verifier.")
    return factory
