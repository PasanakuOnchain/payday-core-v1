from types import SimpleNamespace

import boa
import pytest
from boa.explorer import SESSION
from boa.util.abi import Address, abi_encode

from script import verify
from script.deploy import deploy


def test_verify_rejects_unconfigured_addresses(monkeypatch):
    zero = "0x0000000000000000000000000000000000000000"
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", zero)
    monkeypatch.setattr(verify, "GOAL_BLUEPRINT_ADDRESS", zero)
    monkeypatch.setattr(verify, "ORIGINAL_TREASURY_ADDRESS", zero)
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


def test_etherscan_v2_puts_chainid_on_the_query_string(monkeypatch):
    posted = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "1", "result": "guid"}

    def post(url, data):
        posted["url"] = url
        posted["body_chainid"] = data["chainid"]
        return Response()

    monkeypatch.setattr(SESSION, "post", post)
    verifier = verify.EtherscanV2(
        uri="https://api.etherscan.io/v2/api",
        api_key="test-key",
        chain_id=10143,
    )
    verifier.verify(
        address=Address("0x0000000000000000000000000000000000000001"),
        contract_name="payday_factory",
        solc_json={
            "compiler_version": "v0.4.3",
            "settings": {"outputSelection": {"payday_factory.vy": {"*": []}}},
        },
        constructor_calldata=b"",
    )

    assert posted["url"] == "https://api.etherscan.io/v2/api?chainid=10143"
    assert posted["body_chainid"] == 10143
    assert verifier.uri == "https://api.etherscan.io/v2/api"


def test_verify_uses_a_view_sender_when_no_account_is_loaded(monkeypatch, treasury):
    blueprint, factory = deploy(treasury)
    monkeypatch.setattr(verify, "FACTORY_ADDRESS", str(factory.address))
    monkeypatch.setattr(verify, "GOAL_BLUEPRINT_ADDRESS", str(blueprint.address))
    monkeypatch.setattr(verify, "ORIGINAL_TREASURY_ADDRESS", str(treasury))
    monkeypatch.setattr(boa.env, "eoa", None)
    monkeypatch.setattr(
        verify,
        "get_active_network",
        lambda: SimpleNamespace(
            chain_id=10143,
            explorer_uri="https://api.etherscan.io/v2/api",
            explorer_api_key="test-key",
            is_local_or_forked_network=lambda: False,
        ),
    )
    monkeypatch.setattr(
        boa,
        "verify",
        lambda contract, verifier: SimpleNamespace(wait_for_verification=lambda: None),
    )

    verify.moccasin_main()

    assert boa.env.eoa == verify._VIEW_SENDER


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
