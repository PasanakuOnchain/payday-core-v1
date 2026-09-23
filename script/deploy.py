from moccasin.boa_tools import VyperContract

from src import payday_factory, payday_goal
from tests.utils.constants import (
    URI_COMPLETED,
    URI_CREATED,
    URI_IN_PROGRESS,
)


def deploy(
    treasury: str,
    uri_created: str = URI_CREATED,
    uri_in_progress: str = URI_IN_PROGRESS,
    uri_completed: str = URI_COMPLETED,
) -> tuple[VyperContract, VyperContract]:
    """Deploy the goal blueprint and factory. Returns (blueprint, factory)."""
    blueprint: VyperContract = payday_goal.deploy_as_blueprint()
    factory: VyperContract = payday_factory.deploy(
        blueprint.address,
        treasury,
        uri_created,
        uri_in_progress,
        uri_completed,
    )
    return blueprint, factory


def moccasin_main() -> VyperContract:
    import boa

    treasury = boa.env.eoa
    blueprint, factory = deploy(treasury)
    print("goal blueprint:", blueprint.address)
    print("factory:", factory.address)
    print("treasury:", factory.treasury())
    print("URI_CREATED:", factory.URI_CREATED())
    print("URI_IN_PROGRESS:", factory.URI_IN_PROGRESS())
    print("URI_COMPLETED:", factory.URI_COMPLETED())
    return factory
