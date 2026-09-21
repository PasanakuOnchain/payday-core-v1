"""Existing clones keep the treasury snapshotted at create_goal."""

import boa

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT


def test_set_treasury_does_not_change_existing_goal(factory, owner, asset, saver):
    goal_a, _ = create_goal(factory, asset, saver)
    old_treasury = goal_a.TREASURY()
    assert old_treasury == factory.treasury()

    new_treasury = boa.env.generate_address("new_treasury")
    factory.set_treasury(new_treasury, sender=owner)
    assert factory.treasury() == new_treasury
    assert goal_a.TREASURY() == old_treasury

    goal_b, _ = create_goal(factory, asset, saver)
    assert goal_b.TREASURY() == new_treasury

    fund_and_approve(asset, saver, goal_a.address, MIN_DEPOSIT)
    goal_a.deposit(MIN_DEPOSIT, sender=saver)
    fee_a, _ = goal_a.preview_early_exit()
    old_before = asset.balanceOf(old_treasury)
    new_before = asset.balanceOf(new_treasury)
    goal_a.early_exit(sender=saver)
    assert asset.balanceOf(old_treasury) == old_before + fee_a
    assert asset.balanceOf(new_treasury) == new_before

    fund_and_approve(asset, saver, goal_b.address, MIN_DEPOSIT)
    goal_b.deposit(MIN_DEPOSIT, sender=saver)
    fee_b, _ = goal_b.preview_early_exit()
    old_before = asset.balanceOf(old_treasury)
    new_before = asset.balanceOf(new_treasury)
    goal_b.early_exit(sender=saver)
    assert asset.balanceOf(new_treasury) == new_before + fee_b
    assert asset.balanceOf(old_treasury) == old_before
