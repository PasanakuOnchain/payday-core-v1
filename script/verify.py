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


class EtherscanV2(Etherscan):
    """Etherscan v2 reads `chainid` from the URL, not the POST body."""

    def verify(self, *args, wait: bool = False, **kwargs):
        base = self.uri
        separator = "&" if base and "?" in base else "?"
        self.uri = f"{base}{separator}chainid={self.chain_id}"
        try:
            result = super().verify(*args, wait=False, **kwargs)
        finally:
            self.uri = base
        if wait and result is not None:
            result.wait_for_verification()
            return None
        return result


# Replace these after deployment. No address is read from env or CLI arguments.
# FACTORY_ADDRESS is also read by script/verify_goals.py.
FACTORY_ADDRESS = "0xaDD60a39AabFD6f8eBA056153ac2d291d6624f60"
GOAL_BLUEPRINT_ADDRESS = "0x4E09E94c82e3ba35ECfE8Fa231FcfF7D9DF94984"
ORIGINAL_TREASURY_ADDRESS = "0xC14fF56E720f79d08413CE00533256433D2ED929"
URI_CREATED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_IN_PROGRESS = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_COMPLETED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"

# Live eth_call still needs a from-address. This sender never signs.
_VIEW_SENDER = Address("0xc14ff56e720f79d08413ce00533256433d2ed929")


def ensure_view_sender():
    if boa.env.eoa is None:
        boa.env.eoa = _VIEW_SENDER


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
    ensure_view_sender()
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
    # Titanoboa posts chainid in the form body. Etherscan v2 requires it on
    # the query string, or Monadscan reports the chain id as missing.
    verifier = EtherscanV2(
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
