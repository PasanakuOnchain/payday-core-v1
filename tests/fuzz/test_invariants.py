"""Stateful invariants: conservation of deposits and URI lifecycle."""

import boa
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from moccasin.boa_tools import VyperContract

from script.deploy import deploy
from tests.mocks.deployers import MOCK_ERC20
from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import (
    MIN_DEPOSIT,
    MIN_TARGET,
    URI_COMPLETED,
    URI_CREATED,
    URI_IN_PROGRESS,
)

MAX_DEPOSIT = MIN_DEPOSIT * 50
DAY = 86_400


class GoalStateMachine(RuleBasedStateMachine):
    """One goal. Ghost accounting tracks deposits vs payouts."""

    def __init__(self) -> None:
        super().__init__()
        self.owner: str = boa.env.eoa
        self.saver: str = boa.env.generate_address("inv_saver")
        self.other: str = boa.env.generate_address("inv_other")
        self.treasury: str = boa.env.generate_address("inv_treasury")
        boa.env.set_balance(self.saver, 10**18)
        boa.env.set_balance(self.other, 10**18)

        self.asset: VyperContract = MOCK_ERC20.deploy("USD Coin", "USDC", 6)
        with boa.env.prank(self.owner):
            _, self.factory = deploy(self.treasury)
            self.factory.set_asset_allowed(
                self.asset.address, True, MIN_TARGET, MIN_DEPOSIT
            )

        self.goal, self.token_id = create_goal(self.factory, self.asset, self.saver)
        self.deposited: int = 0
        self.paid_owner: int = 0
        self.paid_treasury: int = 0
        self.closed: bool = False
        self.soulbound: bool = False
        self.nft_owner: str = self.saver

    def _unauthorized(self) -> str:
        return self.other if self.nft_owner == self.saver else self.saver

    def _auth_or_closed_dev(self) -> str:
        if self.closed:
            return "payday_goal: closed"
        return "payday_goal: caller is not nft owner"

    @rule(amount=st.integers(min_value=MIN_DEPOSIT, max_value=MAX_DEPOSIT))
    @precondition(lambda self: not self.closed)
    def deposit(self, amount: int) -> None:
        fund_and_approve(self.asset, self.nft_owner, self.goal.address, amount)
        self.goal.deposit(amount, sender=self.nft_owner)
        self.deposited += amount

    @rule()
    @precondition(
        lambda self: not self.closed and self.goal.principal() >= self.goal.TARGET()
    )
    def complete(self) -> None:
        owner_before = self.asset.balanceOf(self.nft_owner)
        treasury_before = self.asset.balanceOf(self.treasury)
        self.goal.complete(sender=self.nft_owner)
        self.paid_owner += self.asset.balanceOf(self.nft_owner) - owner_before
        self.paid_treasury += self.asset.balanceOf(self.treasury) - treasury_before
        self.closed = True

    @rule()
    @precondition(
        lambda self: not self.closed and 0 < self.goal.principal() < self.goal.TARGET()
    )
    def early_exit(self) -> None:
        owner_before = self.asset.balanceOf(self.nft_owner)
        treasury_before = self.asset.balanceOf(self.treasury)
        self.goal.early_exit(sender=self.nft_owner)
        self.paid_owner += self.asset.balanceOf(self.nft_owner) - owner_before
        self.paid_treasury += self.asset.balanceOf(self.treasury) - treasury_before
        self.closed = True

    @rule()
    @precondition(lambda self: not self.soulbound)
    def transfer_nft(self) -> None:
        recipient = self.other if self.nft_owner == self.saver else self.saver
        self.factory.transferFrom(
            self.nft_owner, recipient, self.token_id, sender=self.nft_owner
        )
        self.nft_owner = recipient

    @rule()
    @precondition(lambda self: not self.soulbound)
    def disable_transfers(self) -> None:
        self.factory.disable_transfers(self.token_id, sender=self.nft_owner)
        self.soulbound = True

    @rule(seconds=st.integers(min_value=1, max_value=7 * DAY))
    def time_travel(self, seconds: int) -> None:
        boa.env.time_travel(seconds=seconds)

    @rule()
    def unauthorized_deposit_reverts(self) -> None:
        caller = self._unauthorized()
        with boa.env.prank(caller), boa.reverts(dev=self._auth_or_closed_dev()):
            self.goal.deposit(MIN_DEPOSIT)

    @rule()
    def unauthorized_complete_reverts(self) -> None:
        caller = self._unauthorized()
        with boa.env.prank(caller), boa.reverts(dev=self._auth_or_closed_dev()):
            self.goal.complete()

    @rule()
    def unauthorized_early_exit_reverts(self) -> None:
        caller = self._unauthorized()
        with boa.env.prank(caller), boa.reverts(dev=self._auth_or_closed_dev()):
            self.goal.early_exit()

    @invariant()
    def invariant_conservation(self) -> None:
        held = self.asset.balanceOf(self.goal.address)
        assert held + self.paid_owner + self.paid_treasury == self.deposited
        if self.closed:
            assert self.goal.principal() == 0
            assert held == 0
            assert self.goal.closed() is True

    @invariant()
    def invariant_lifecycle(self) -> None:
        principal = self.goal.principal()
        uri = self.factory.tokenURI(self.token_id)
        closed = self.goal.closed()
        bps = self.goal.penalty_bps()

        assert 0 <= bps <= self.goal.START_PENALTY_BPS()
        assert closed is self.closed
        assert self.factory.ownerOf(self.token_id) == self.nft_owner

        if closed:
            assert uri == URI_COMPLETED
            assert principal == 0
        elif principal == 0:
            assert uri == URI_CREATED
        else:
            assert uri == URI_IN_PROGRESS


def test_goal_invariants() -> None:
    run_state_machine_as_test(
        GoalStateMachine,
        settings=settings(
            max_examples=40,
            stateful_step_count=15,
            deadline=None,
        ),
    )
