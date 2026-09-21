"""Vault create → park → yield → complete pays principal and surplus."""

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT, URI_COMPLETED, URI_IN_PROGRESS


def test_vault_complete_pays_principal_and_surplus(
    factory, asset, saver, treasury, vault
):
    goal, token_id = create_goal(factory, asset, saver, vault=vault.address)
    target = goal.TARGET()
    fund_and_approve(asset, saver, goal.address, target)
    goal.deposit(target, sender=saver)

    assert asset.balanceOf(goal.address) == 0
    assert vault.convertToAssets(vault.balanceOf(goal.address)) == target
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS

    yield_amount = MIN_DEPOSIT
    asset.mint(saver, yield_amount)
    asset.approve(vault.address, yield_amount, sender=saver)
    vault.simulate_yield(yield_amount, sender=saver)
    assert vault.convertToAssets(vault.balanceOf(goal.address)) == target + yield_amount

    saver_before = asset.balanceOf(saver)
    treasury_before = asset.balanceOf(treasury)
    goal.complete(sender=saver)

    assert goal.closed() is True
    assert goal.principal() == 0
    assert vault.balanceOf(goal.address) == 0
    assert asset.balanceOf(saver) == saver_before + target
    assert asset.balanceOf(treasury) == treasury_before + yield_amount
    assert factory.tokenURI(token_id) == URI_COMPLETED
