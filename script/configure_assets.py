"""Allowlist the supported assets on the deployed factory.

Uses FACTORY_ADDRESS from script/verify.py. Asset addresses and dust floors
are the hardcoded lists below, selected by chain id. Nothing is read from
the environment or CLI arguments. The active account must be the factory owner.

Floors are token base units: 10 units minimum target, 1 unit minimum deposit.

Run:
    mox run configure_assets --network monad
    mox run configure_assets --network monad-testnet
"""

from collections import namedtuple

import boa
from boa.util.abi import Address
from moccasin.config import get_active_network

from script import verify
from src import payday_factory

Asset = namedtuple("Asset", "address min_target min_deposit")


def _asset(address: str, decimals: int) -> tuple[str, int, int]:
    unit = 10**decimals
    return (address, 10 * unit, unit)


# (address, min_target, min_deposit). Mainnet entries are the canonical
# 6-decimal stables. Testnet entries are the deployed Payday mocks.
ASSETS = {
    143: (
        _asset("0x754704Bc059F8C67012fEd69BC8A327a5aafb603", 6),  # USDC
        _asset("0xe7cd86e13AC4309349F30B3435a9d337750fC82D", 6),  # USDT0
    ),
    10143: (
        _asset("0x244aDdF22c4500c55Ab4F5ee18506a953B2b8A90", 6),  # mock USDC
        _asset("0xA0aC4fc6ed42A5d1ABA1a8fE1C5b66168A29b33E", 6),  # mock USDT0
        _asset("0x0d3508A5bEB6DbF4C67282c38fb08674Ae2d1280", 18), # mock WMON
    ),
}


def configured_assets(chain_id: int) -> tuple[Asset, ...]:
    listed = ASSETS.get(chain_id)
    if not listed:
        raise ValueError(f"No hardcoded assets for chain {chain_id}.")
    assets = tuple(
        Asset(Address(address), min_target, min_deposit)
        for address, min_target, min_deposit in listed
    )
    if any(int(asset.address, 16) == 0 for asset in assets):
        raise ValueError("Hardcoded asset list contains the zero address.")
    if any(
        asset.min_deposit == 0 or asset.min_target < asset.min_deposit
        for asset in assets
    ):
        raise ValueError("Hardcoded asset floor is invalid.")
    if len({asset.address for asset in assets}) != len(assets):
        raise ValueError("Hardcoded asset list contains a duplicate.")
    return assets


def allow_assets(factory, assets: tuple[Asset, ...]) -> int:
    """Owner-allow each asset at its hardcoded dust floors."""
    print(f"factory: {factory.address}")
    print(f"owner: {factory.owner()}")
    for asset in assets:
        print(
            f"allowlisting {asset.address} "
            f"min_target={asset.min_target} min_deposit={asset.min_deposit}"
        )
        factory.set_asset_allowed(
            asset.address, True, asset.min_target, asset.min_deposit
        )
        allowed, min_target, min_deposit = factory.asset_config(asset.address)
        if (
            not allowed
            or min_target != asset.min_target
            or min_deposit != asset.min_deposit
        ):
            raise RuntimeError(f"Allowlist write did not stick for {asset.address}.")
        print(f"allowed {asset.address}")
    print(f"allowlisted {len(assets)} assets")
    return len(assets)


def moccasin_main():
    network = get_active_network()
    if network.chain_id not in ASSETS or network.is_local_or_forked_network():
        raise ValueError("Select the live monad or monad-testnet network.")

    factory_address = Address(verify.FACTORY_ADDRESS)
    if int(factory_address, 16) == 0:
        raise ValueError("Fill in FACTORY_ADDRESS in script/verify.py.")
    if not boa.env.get_code(factory_address):
        raise ValueError("No factory code at the hardcoded address on this network.")

    factory = payday_factory.at(factory_address)
    if factory.owner() != boa.env.eoa:
        raise ValueError("Active account is not the factory owner.")

    assets = configured_assets(network.chain_id)
    for asset in assets:
        if not boa.env.get_code(asset.address):
            raise ValueError(f"No token code at hardcoded address {asset.address}.")

    allow_assets(factory, assets)
    return factory
