from types import SimpleNamespace

import boa
import pytest
from boa.util.abi import abi_encode

from script import verify
from script.deploy import deploy
from tests.utils import now
from tests.utils.constants import DEFAULT_TARGET, MIN_DEPOSIT, MIN_DURATION, MIN_TARGET


def test_verify_rejects_unconfigured_addresses():
    with pytest.raises(ValueError, match="hardcoded deployment addresses"):
        verify.deployment_addresses()


def test_verify_existing_factory_preserves_constructor_and_chain(monkeypatch, treasury):
    blueprint, factory = deploy(treasury)
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(verify, "GOAL_BLUEPRINT_ADDRESS", str(blueprint.address))
    monkeypatch.setattr(verify, "ORIGINAL_TREASURY_ADDRESS", str(treasury))
    network = SimpleNamespace(
        chain_id=10143,
        explorer_uri="https://api.etherscan.io/v2/api",
        explorer_api_key="test-key",
        is_local_or_forked_network=lambda: False,
    )
    monkeypatch.setattr(verify, "get_active_network", lambda: network)
    captured = {}

    def submit(contract, verifier):
        captured["chain"] = verifier.chain_id
        captured["constructor"] = contract.ctor_calldata
        return SimpleNamespace(
            wait_for_verification=lambda: captured.update(waited=True)
        )

    monkeypatch.setattr(boa, "verify", submit)
    verified = verify.moccasin_main()
    assert verified.address == factory.address
    assert captured["chain"] == 10143
    assert captured["waited"]
    assert captured["constructor"] == abi_encode(
        "(address,address,string,string,string)",
        (
            blueprint.address,
            treasury,
            verify.URI_CREATED,
            verify.URI_IN_PROGRESS,
            verify.URI_COMPLETED,
        ),
    )


def test_verify_rejects_local_network(monkeypatch, treasury):
    blueprint, factory = deploy(treasury)
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(verify, "GOAL_BLUEPRINT_ADDRESS", str(blueprint.address))
    monkeypatch.setattr(verify, "ORIGINAL_TREASURY_ADDRESS", str(treasury))
    monkeypatch.setattr(
        verify, "get_active_network", lambda: SimpleNamespace(chain_id=31337)
    )
    with pytest.raises(ValueError, match="live monad"):
        verify.moccasin_main()


def test_verify_goal_uses_immutable_constructor(monkeypatch, treasury, asset):
    blueprint, factory = deploy(treasury)
    factory.set_asset_allowed(asset.address, True, MIN_TARGET, MIN_DEPOSIT)
    goal_address, _ = factory.create_goal(
        asset.address, DEFAULT_TARGET, now() + MIN_DURATION
    )
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(verify, "GOAL_BLUEPRINT_ADDRESS", str(blueprint.address))
    monkeypatch.setattr(verify, "ORIGINAL_TREASURY_ADDRESS", str(treasury))
    monkeypatch.setattr(verify, "GOAL_ADDRESS", str(goal_address))
    monkeypatch.setattr(
        verify,
        "get_active_network",
        lambda: SimpleNamespace(
            chain_id=143,
            explorer_uri="https://api.etherscan.io/v2/api",
            explorer_api_key="test-key",
            is_local_or_forked_network=lambda: False,
        ),
    )
    submitted = []

    def submit(contract, verifier):
        submitted.append((contract.address, contract.ctor_calldata, verifier.chain_id))
        return SimpleNamespace(wait_for_verification=lambda: None)

    monkeypatch.setattr(boa, "verify", submit)
    verify.moccasin_main()
    assert [item[0] for item in submitted] == [factory.address, goal_address]
    assert all(item[2] == 143 for item in submitted)
    from boa.util.abi import abi_decode

    args = abi_decode(
        "(address,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256)",
        submitted[1][1],
    )
    assert args[0] == factory.address
    assert args[1] == asset.address
    assert args[2] == treasury
    assert args[4] == DEFAULT_TARGET
    assert args[6] - args[5] == MIN_DURATION
