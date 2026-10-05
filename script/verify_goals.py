"""Verify every goal the factory has minted. Never deploy or sign.

Uses FACTORY_ADDRESS from script/verify.py. Run periodically:
mox run verify_goals --network monad-testnet (or --network monad).
Goals whose explorer source is already present are skipped.
Only the explorer API credential comes from moccasin.toml / .env.
"""

import boa
from boa.explorer import Etherscan
from boa.util.abi import Address, abi_encode
from moccasin.config import get_active_network

from script import verify
from src import payday_factory, payday_goal

_GOAL_CTOR = (
    "(address,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256)"
)


def configured_factory_address():
    address = Address(verify.FACTORY_ADDRESS)
    if int(address, 16) == 0:
        raise ValueError("Fill in FACTORY_ADDRESS in script/verify.py.")
    return address


def goal_ctor_calldata(goal):
    return abi_encode(
        _GOAL_CTOR,
        (
            goal.FACTORY(),
            goal.ASSET(),
            goal.TREASURY(),
            goal.VAULT(),
            goal.TARGET(),
            goal.START_TIME(),
            goal.END_TIME(),
            goal.START_PENALTY_BPS(),
            goal.TOKEN_ID(),
            goal.MIN_DEPOSIT(),
        ),
    )


def explorer_source_payload(verifier, address):
    return verifier._fetch(
        module="contract",
        action="getsourcecode",
        address=address,
    )


def source_is_present(payload):
    result = payload.get("result")
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        raise ValueError("Explorer returned an unexpected source-code payload.")
    return bool(str(result[0].get("SourceCode", "")).strip())


def _already_verified_message(error):
    return "already verified" in str(error).lower()


def moccasin_main():
    factory_address = configured_factory_address()
    network = get_active_network()
    if network.chain_id not in (143, 10143) or network.is_local_or_forked_network():
        raise ValueError("Select the live monad or monad-testnet network.")
    if not network.explorer_api_key or network.explorer_api_key.startswith("$"):
        raise ValueError("Set ETHERSCAN_API_KEY for the configured explorer.")
    if not boa.env.get_code(factory_address):
        raise ValueError("No factory code at the hardcoded address on this network.")

    factory = payday_factory.at(factory_address)
    verifier = Etherscan(
        uri=network.explorer_uri,
        api_key=network.explorer_api_key,
        chain_id=network.chain_id,
    )
    supply = factory.totalSupply()
    print(f"Factory {factory_address} has {supply} goal(s).")

    verified = 0
    skipped = 0
    failures = []
    for index in range(supply):
        token_id = factory.tokenByIndex(index)
        goal_address = Address(factory.goals(token_id))
        if int(goal_address, 16) == 0:
            raise ValueError(f"Factory token {token_id} has no goal.")

        if source_is_present(explorer_source_payload(verifier, goal_address)):
            print(f"Skip token {token_id} already verified: {goal_address}")
            skipped += 1
            continue

        goal = payday_goal.at(goal_address)
        if (
            Address(goal.FACTORY()) != factory_address
            or Address(factory.goals(goal.TOKEN_ID())) != goal_address
        ):
            raise ValueError(f"Goal {goal_address} is not registered with this factory.")
        goal.ctor_calldata = goal_ctor_calldata(goal)
        print(f"Submitting token {token_id}: {goal_address}")
        try:
            boa.verify(goal, verifier).wait_for_verification()
        except (ValueError, TimeoutError) as error:
            if _already_verified_message(error):
                print(f"Skip token {token_id} already verified: {goal_address}")
                skipped += 1
                continue
            print(f"Goal verification failed for {goal_address}: {error}")
            failures.append(goal_address)
            continue
        print(f"Goal verified: {goal_address}")
        verified += 1

    print(f"Goals verified: {verified}. Already verified: {skipped}. Failed: {len(failures)}.")
    if failures:
        joined = ", ".join(str(address) for address in failures)
        raise ValueError(f"Goal verification failed for: {joined}")
    return verified, skipped
