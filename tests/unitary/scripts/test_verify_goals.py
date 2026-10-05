from types import SimpleNamespace

import boa
import pytest
from boa.util.abi import abi_decode

from script import verify, verify_goals
from tests.utils import create_goal
from tests.utils.constants import DAY, MIN_DURATION


def _network(chain_id=10143):
    return SimpleNamespace(
        chain_id=chain_id,
        explorer_uri="https://api.etherscan.io/v2/api",
        explorer_api_key="test-key",
        is_local_or_forked_network=lambda: False,
    )


def _patch_live(monkeypatch, factory, chain_id=10143):
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(verify_goals, "get_active_network", lambda: _network(chain_id))


def _unverified(_verifier, _address):
    return {"result": [{"SourceCode": ""}]}


def test_verify_goals_rejects_unconfigured_factory():
    with pytest.raises(ValueError, match="FACTORY_ADDRESS"):
        verify_goals.configured_factory_address()


def test_verify_goals_rejects_local_network(monkeypatch, factory):
    _patch_live(monkeypatch, factory, chain_id=31337)
    with pytest.raises(ValueError, match="live monad"):
        verify_goals.moccasin_main()


def test_verify_goals_empty_factory_submits_nothing(monkeypatch, factory):
    _patch_live(monkeypatch, factory)
    monkeypatch.setattr(boa, "verify", lambda *_args, **_kwargs: pytest.fail("verify called"))
    monkeypatch.setattr(
        verify_goals,
        "explorer_source_payload",
        lambda *_args, **_kwargs: pytest.fail("explorer called"),
    )
    assert verify_goals.moccasin_main() == (0, 0)


def test_verify_goals_submits_each_unverified_goal(monkeypatch, factory, asset, saver):
    first, first_id = create_goal(factory, asset, saver)
    second, second_id = create_goal(
        factory, asset, saver, duration=MIN_DURATION + DAY
    )
    _patch_live(monkeypatch, factory)
    monkeypatch.setattr(verify_goals, "explorer_source_payload", _unverified)
    submitted = []

    def submit(contract, verifier):
        submitted.append((contract.address, contract.ctor_calldata, verifier.chain_id))
        return SimpleNamespace(wait_for_verification=lambda: None)

    monkeypatch.setattr(boa, "verify", submit)
    assert verify_goals.moccasin_main() == (2, 0)
    assert [item[0] for item in submitted] == [first.address, second.address]
    assert all(item[2] == 10143 for item in submitted)

    first_args = abi_decode(verify_goals._GOAL_CTOR, submitted[0][1])
    second_args = abi_decode(verify_goals._GOAL_CTOR, submitted[1][1])
    assert first_args[0] == factory.address
    assert first_args[1] == asset.address
    assert first_args[2] == factory.treasury()
    assert first_args[8] == first_id
    assert second_args[8] == second_id
    assert second_args[6] - second_args[5] == MIN_DURATION + DAY


def test_verify_goals_skips_source_already_on_explorer(
    monkeypatch, factory, asset, saver
):
    first, _ = create_goal(factory, asset, saver)
    second, _ = create_goal(factory, asset, saver, duration=MIN_DURATION + DAY)
    _patch_live(monkeypatch, factory)

    def payload(_verifier, address):
        source = "verified-source" if address == first.address else ""
        return {"result": [{"SourceCode": source}]}

    monkeypatch.setattr(verify_goals, "explorer_source_payload", payload)
    submitted = []

    def submit(contract, _verifier):
        submitted.append(contract.address)
        return SimpleNamespace(wait_for_verification=lambda: None)

    monkeypatch.setattr(boa, "verify", submit)
    assert verify_goals.moccasin_main() == (1, 1)
    assert submitted == [second.address]


def test_verify_goals_skips_already_verified_submission_error(
    monkeypatch, factory, asset, saver
):
    first, _ = create_goal(factory, asset, saver)
    second, _ = create_goal(factory, asset, saver, duration=MIN_DURATION + DAY)
    _patch_live(monkeypatch, factory)
    monkeypatch.setattr(verify_goals, "explorer_source_payload", _unverified)
    submitted = []

    def submit(contract, _verifier):
        submitted.append(contract.address)
        if contract.address == first.address:
            raise ValueError("Failed to verify: Contract source code already verified")
        return SimpleNamespace(wait_for_verification=lambda: None)

    monkeypatch.setattr(boa, "verify", submit)
    assert verify_goals.moccasin_main() == (1, 1)
    assert submitted == [first.address, second.address]


def test_verify_goals_continues_after_a_failure(monkeypatch, factory, asset, saver):
    first, _ = create_goal(factory, asset, saver)
    second, _ = create_goal(factory, asset, saver, duration=MIN_DURATION + DAY)
    _patch_live(monkeypatch, factory)
    monkeypatch.setattr(verify_goals, "explorer_source_payload", _unverified)
    submitted = []

    def submit(contract, _verifier):
        submitted.append(contract.address)
        if contract.address == first.address:
            raise ValueError("Failed to verify: bytecode mismatch")
        return SimpleNamespace(wait_for_verification=lambda: None)

    monkeypatch.setattr(boa, "verify", submit)
    with pytest.raises(ValueError, match=str(first.address)):
        verify_goals.moccasin_main()
    assert submitted == [first.address, second.address]


def test_source_is_present_rejects_unexpected_payload():
    with pytest.raises(ValueError, match="unexpected source-code"):
        verify_goals.source_is_present({"result": "nope"})
