"""Phase-3 optional ERC-4626 park + skim."""

import boa

from tests.utils import create_goal, filter_logs, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT

EMPTY = "0x0000000000000000000000000000000000000000"


def test_skim_reverts_without_surplus(factory, asset, saver):
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    with boa.reverts(dev="payday_goal: no surplus"):
        goal.skim_yield()


def test_skim_donated_surplus_to_treasury(factory, asset, saver, treasury):
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    surplus = MIN_DEPOSIT
    asset.mint(goal.address, surplus)
    treasury_before = asset.balanceOf(treasury)
    goal.skim_yield()
    logs = filter_logs(goal, "YieldSkimmed")

    assert asset.balanceOf(treasury) == treasury_before + surplus
    assert goal.principal() == MIN_DEPOSIT
    assert asset.balanceOf(goal.address) == MIN_DEPOSIT
    assert len(logs) == 1
    assert logs[0].surplus == surplus


def test_skim_yield_anyone_may_call(factory, asset, saver, other, treasury):
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    surplus = MIN_DEPOSIT
    asset.mint(goal.address, surplus)
    treasury_before = asset.balanceOf(treasury)
    goal.skim_yield(sender=other)

    assert asset.balanceOf(treasury) == treasury_before + surplus
    assert goal.principal() == MIN_DEPOSIT


def test_vault_park_and_complete(factory, asset, saver, vault):
    goal, _ = create_goal(factory, asset, saver, vault=vault.address)
    assert goal.VAULT() == vault.address
    assert goal.VAULT() != EMPTY

    target = goal.TARGET()
    fund_and_approve(asset, saver, goal.address, target)
    goal.deposit(target, sender=saver)

    assert asset.balanceOf(goal.address) == 0
    assert vault.convertToAssets(vault.balanceOf(goal.address)) == target
    assert goal.principal() == target

    saver_before = asset.balanceOf(saver)
    goal.complete(sender=saver)
    assert asset.balanceOf(saver) == saver_before + target
    assert vault.balanceOf(goal.address) == 0


def test_vault_skim_yield_to_treasury(factory, asset, saver, treasury, vault):
    goal, _ = create_goal(factory, asset, saver, vault=vault.address)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    yield_amount = MIN_DEPOSIT
    asset.mint(saver, yield_amount)
    asset.approve(vault.address, yield_amount, sender=saver)
    vault.simulate_yield(yield_amount, sender=saver)

    assert (
        vault.convertToAssets(vault.balanceOf(goal.address))
        == MIN_DEPOSIT + yield_amount
    )

    treasury_before = asset.balanceOf(treasury)
    goal.skim_yield()
    assert asset.balanceOf(treasury) == treasury_before + yield_amount
    assert goal.principal() == MIN_DEPOSIT


def test_vault_shortfall_blocks_deposit_and_skim(factory, asset, saver, vault):
    goal, _ = create_goal(factory, asset, saver, vault=vault.address)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    vault.simulate_loss(MIN_DEPOSIT // 2)

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: vault shortfall"):
        goal.deposit(MIN_DEPOSIT)

    with boa.reverts(dev="payday_goal: vault shortfall"):
        goal.skim_yield()


def test_vault_early_exit_withdraws_from_4626(factory, asset, saver, treasury, vault):
    goal, _ = create_goal(factory, asset, saver, vault=vault.address)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    assert asset.balanceOf(goal.address) == 0
    assert vault.convertToAssets(vault.balanceOf(goal.address)) == MIN_DEPOSIT

    fee, net = goal.preview_early_exit()
    treasury_before = asset.balanceOf(treasury)
    saver_before = asset.balanceOf(saver)
    goal.early_exit(sender=saver)

    assert goal.closed() is True
    assert vault.balanceOf(goal.address) == 0
    assert asset.balanceOf(treasury) == treasury_before + fee
    assert asset.balanceOf(saver) == saver_before + net
