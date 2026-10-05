from types import SimpleNamespace

import boa
import pytest
from boa.util.abi import abi_encode

from script import verify
from script.deploy import deploy


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
