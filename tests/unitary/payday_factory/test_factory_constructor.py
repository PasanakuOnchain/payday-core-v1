"""Factory constructor argument validation."""

import boa
from src import payday_factory, payday_goal

from tests.utils.constants import URI_COMPLETED, URI_CREATED, URI_IN_PROGRESS

EMPTY = "0x0000000000000000000000000000000000000000"


def test_constructor_zero_blueprint_reverts(treasury):
    with boa.reverts(dev="payday_factory: zero blueprint"):
        payday_factory.deploy(
            EMPTY,
            treasury,
            URI_CREATED,
            URI_IN_PROGRESS,
            URI_COMPLETED,
        )


def test_constructor_zero_treasury_reverts():
    blueprint = payday_goal.deploy_as_blueprint()
    with boa.reverts(dev="payday_factory: zero treasury"):
        payday_factory.deploy(
            blueprint.address,
            EMPTY,
            URI_CREATED,
            URI_IN_PROGRESS,
            URI_COMPLETED,
        )


def test_constructor_empty_created_uri_reverts(treasury):
    blueprint = payday_goal.deploy_as_blueprint()
    with boa.reverts(dev="payday_factory: empty created uri"):
        payday_factory.deploy(
            blueprint.address,
            treasury,
            "",
            URI_IN_PROGRESS,
            URI_COMPLETED,
        )


def test_constructor_empty_progress_uri_reverts(treasury):
    blueprint = payday_goal.deploy_as_blueprint()
    with boa.reverts(dev="payday_factory: empty progress uri"):
        payday_factory.deploy(
            blueprint.address,
            treasury,
            URI_CREATED,
            "",
            URI_COMPLETED,
        )


def test_constructor_empty_completed_uri_reverts(treasury):
    blueprint = payday_goal.deploy_as_blueprint()
    with boa.reverts(dev="payday_factory: empty completed uri"):
        payday_factory.deploy(
            blueprint.address,
            treasury,
            URI_CREATED,
            URI_IN_PROGRESS,
            "",
        )
