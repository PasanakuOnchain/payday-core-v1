from types import SimpleNamespace

import pytest
from boa.util.abi import Address

from script import configure_assets, verify
from script.deploy import deploy
from tests.mocks.deployers import MOCK_ERC20
from tests.utils.constants import MIN_DEPOSIT, MIN_TARGET

MAINNET_USDC = "0x754704Bc059F8C67012fEd69BC8A327a5aafb603"
MAINNET_USDT0 = "0xe7cd86e13AC4309349F30B3435a9d337750fC82D"
TESTNET_USDC = "0x244aDdF22c4500c55Ab4F5ee18506a953B2b8A90"
TESTNET_USDT0 = "0xA0aC4fc6ed42A5d1ABA1a8fE1C5b66168A29b33E"
TESTNET_WMON = "0x0d3508A5bEB6DbF4C67282c38fb08674Ae2d1280"
WMON_UNIT = 10**18


def _network(chain_id=143, forked=False):
    return SimpleNamespace(
        chain_id=chain_id,
        is_local_or_forked_network=lambda: forked,
    )


def test_configured_assets_match_the_hardcoded_lists():
    mainnet = configure_assets.configured_assets(143)
    assert [asset.address for asset in mainnet] == [MAINNET_USDC, MAINNET_USDT0]
    assert all(
        asset.min_target == MIN_TARGET and asset.min_deposit == MIN_DEPOSIT
        for asset in mainnet
    )

    testnet = configure_assets.configured_assets(10143)
    assert [asset.address for asset in testnet] == [
        TESTNET_USDC,
        TESTNET_USDT0,
        TESTNET_WMON,
    ]
    assert testnet[0].min_target == MIN_TARGET
    assert testnet[0].min_deposit == MIN_DEPOSIT
    assert testnet[1].min_target == MIN_TARGET
    assert testnet[1].min_deposit == MIN_DEPOSIT
    assert testnet[2].min_target == 10 * WMON_UNIT
    assert testnet[2].min_deposit == WMON_UNIT


def test_configured_assets_rejects_unknown_chain():
    with pytest.raises(ValueError, match="No hardcoded assets"):
        configure_assets.configured_assets(1)


def test_configured_assets_rejects_zero_and_duplicates(monkeypatch):
    zero = "0x0000000000000000000000000000000000000000"
    monkeypatch.setitem(
        configure_assets.ASSETS, 143, ((zero, MIN_TARGET, MIN_DEPOSIT),)
    )
    with pytest.raises(ValueError, match="zero address"):
        configure_assets.configured_assets(143)

    monkeypatch.setitem(
        configure_assets.ASSETS,
        143,
        (
            (MAINNET_USDC, MIN_TARGET, MIN_DEPOSIT),
            (MAINNET_USDC, MIN_TARGET, MIN_DEPOSIT),
        ),
    )
    with pytest.raises(ValueError, match="duplicate"):
        configure_assets.configured_assets(143)


def test_allow_assets_writes_each_floor(owner):
    _, factory = deploy(owner)
    first = MOCK_ERC20.deploy("USD Coin", "USDC", 6)
    second = MOCK_ERC20.deploy("Wrapped MON", "WMON", 18)
    assets = (
        configure_assets.Asset(Address(first.address), MIN_TARGET, MIN_DEPOSIT),
        configure_assets.Asset(Address(second.address), 10 * WMON_UNIT, WMON_UNIT),
    )

    assert configure_assets.allow_assets(factory, assets) == 2
    for asset in assets:
        allowed, min_target, min_deposit = factory.asset_config(asset.address)
        assert allowed is True
        assert min_target == asset.min_target
        assert min_deposit == asset.min_deposit


def test_moccasin_main_rejects_unconfigured_factory(monkeypatch):
    monkeypatch.setattr(configure_assets, "get_active_network", lambda: _network())
    with pytest.raises(ValueError, match="FACTORY_ADDRESS"):
        configure_assets.moccasin_main()


def test_moccasin_main_rejects_local_network(monkeypatch):
    monkeypatch.setattr(configure_assets, "get_active_network", lambda: _network(31337))
    with pytest.raises(ValueError, match="live monad"):
        configure_assets.moccasin_main()


def test_moccasin_main_rejects_missing_token_code(monkeypatch, owner):
    _, factory = deploy(owner)
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(configure_assets, "get_active_network", lambda: _network())
    with pytest.raises(ValueError, match="No token code"):
        configure_assets.moccasin_main()


def test_moccasin_main_allowlists_hardcoded_assets(monkeypatch, owner):
    _, factory = deploy(owner)
    usdc = MOCK_ERC20.deploy("USD Coin", "USDC", 6)
    usdt0 = MOCK_ERC20.deploy("USDT0", "USDT0", 6)
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setitem(
        configure_assets.ASSETS,
        143,
        (
            (str(usdc.address), MIN_TARGET, MIN_DEPOSIT),
            (str(usdt0.address), MIN_TARGET, MIN_DEPOSIT),
        ),
    )
    monkeypatch.setattr(configure_assets, "get_active_network", lambda: _network())

    configured = configure_assets.moccasin_main()

    assert configured.address == factory.address
    for asset in (usdc.address, usdt0.address):
        allowed, min_target, min_deposit = factory.asset_config(asset)
        assert allowed is True
        assert min_target == MIN_TARGET
        assert min_deposit == MIN_DEPOSIT
