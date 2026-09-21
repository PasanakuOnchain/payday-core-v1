# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Payday Goal
@custom:contract-name payday_goal
@license GNU Affero General Public License v3.0 only
@author rafael-abuawad
@notice Single-asset savings goal deployed as an EIP-5202 blueprint clone.
@dev The factory ERC-721 owner may deposit, complete, or early-exit.
     Free unlock iff `principal >= target`. Under target, early exit is
     all-or-nothing with a linear time-decaying penalty to treasury.
     Optional ERC-4626 vault: v1 factory passes `empty(address)`.
"""


from ethereum.ercs import IERC20


from ethereum.ercs import IERC721


from ethereum.ercs import IERC4626


from interfaces import IPaydayFactory


# @dev Basis points denominator for `fee = principal * bps / BPS_DENOMINATOR`.
BPS_DENOMINATOR: public(constant(uint256)) = 10_000


# @dev Factory ERC-721 that minted `TOKEN_ID` and authorises goal actions.
FACTORY: public(immutable(address))


# @dev ERC-20 held (or parked in `VAULT`) by this goal.
ASSET: public(immutable(address))


# @dev Recipient of early-exit fees and skimmed surplus for this clone.
TREASURY: public(immutable(address))


# @dev Optional IERC4626. `empty(address)` disables yield parking and withdraw.
VAULT: public(immutable(address))


# @dev Nominal principal required for a free `complete()`.
TARGET: public(immutable(uint256))


# @dev Timestamp when the penalty curve starts (`create_goal` block time).
START_TIME: public(immutable(uint256))


# @dev Timestamp when the penalty reaches zero.
END_TIME: public(immutable(uint256))


# @dev Penalty in bps at `START_TIME`; decays linearly to 0 at `END_TIME`.
START_PENALTY_BPS: public(immutable(uint256))


# @dev Factory ERC-721 token that gates `deposit` / `complete` / `early_exit`.
# @notice Auth is `msg.sender == IERC721(FACTORY).ownerOf(TOKEN_ID)`.
TOKEN_ID: public(immutable(uint256))


# @dev Minimum `amount` accepted by `deposit`, copied from factory allowlist.
MIN_DEPOSIT: public(immutable(uint256))


# @dev Nominal principal deposited by the NFT owner (not vault NAV).
principal: public(uint256)


# @dev `True` after a successful `complete` or `early_exit`; blocks further use.
closed: public(bool)


# @dev Emitted when the NFT owner deposits `ASSET` into this goal.
event Deposit:
    owner: indexed(address)
    amount: uint256
    principal: uint256


# @dev Emitted when `principal >= TARGET` and funds are returned to the owner.
event Completed:
    owner: indexed(address)
    amount: uint256


# @dev Emitted on all-or-nothing exit under target.
#      Fee goes to treasury; net goes to the NFT owner.
event EarlyExit:
    owner: indexed(address)
    fee: uint256
    net: uint256
    penalty_bps: uint256


# @dev Emitted when surplus above nominal `principal` is sent to `TREASURY`.
event YieldSkimmed:
    surplus: uint256


@deploy
@payable
def __init__(
    factory: address,
    asset: address,
    treasury: address,
    vault: address,
    target: uint256,
    start_time: uint256,
    end_time: uint256,
    start_penalty_bps: uint256,
    token_id: uint256,
    min_deposit: uint256,
):
    """
    @dev Blueprint constructor. All configuration is immutable after clone.
    @param factory Payday factory (ERC-721) that minted `token_id`.
    @param asset ERC-20 held by this goal.
    @param treasury Recipient of early-exit fees and skimmed surplus.
    @param vault Optional IERC4626; `empty(address)` disables yield.
    @param target Principal required for a free complete.
    @param start_time Timestamp when the penalty curve starts.
    @param end_time Timestamp when the penalty reaches zero.
    @param start_penalty_bps Penalty in bps at `start_time`.
    @param token_id Factory ERC-721 token that gates this goal.
    @param min_deposit Minimum amount accepted by `deposit`.
    """
    assert factory != empty(address), "payday_goal: zero factory"
    assert asset != empty(address), "payday_goal: zero asset"
    assert treasury != empty(address), "payday_goal: zero treasury"
    assert target != empty(uint256), "payday_goal: zero target"
    assert end_time > start_time, "payday_goal: bad times"
    assert min_deposit != empty(uint256), "payday_goal: zero min deposit"

    FACTORY = factory
    ASSET = asset
    TREASURY = treasury
    VAULT = vault
    TARGET = target
    START_TIME = start_time
    END_TIME = end_time
    START_PENALTY_BPS = start_penalty_bps
    TOKEN_ID = token_id
    MIN_DEPOSIT = min_deposit


@external
@nonreentrant
def deposit(amount: uint256):
    """
    @dev Pulls `amount` of `ASSET` from the NFT owner into this goal.
    @notice First successful deposit asks the factory to set InProgress URI.
            If a vault is configured, assets are deposited there after pull.
    @param amount Token amount; must be at least `MIN_DEPOSIT`.
    """
    self._check_open()
    self._check_nft_owner()
    assert amount >= MIN_DEPOSIT, "payday_goal: amount below min"
    self._assert_vault_healthy()

    first_deposit: bool = self.principal == empty(uint256)
    success: bool = extcall IERC20(ASSET).transferFrom(msg.sender, self, amount)
    assert success, "payday_goal: transferFrom failed"

    self.principal += amount
    self._park(amount)

    if first_deposit:
        extcall IPaydayFactory(FACTORY).set_goal_uri_in_progress(TOKEN_ID)

    log Deposit(owner=msg.sender, amount=amount, principal=self.principal)


@external
@view
def penalty_bps() -> uint256:
    """
    @dev Linear penalty from `START_PENALTY_BPS` at `START_TIME` to 0 at `END_TIME`.
    @return uint256 Current penalty in basis points.
    """
    return self._penalty_bps()


@external
@view
def preview_early_exit() -> (uint256, uint256):
    """
    @dev Quotes the current early-exit fee (treasury) and net (owner).
    @notice Fee rounds down (favours the saver). Mul before div.
    @return fee Amount sent to treasury on `early_exit`.
    @return net Amount sent to the NFT owner on `early_exit`.
    """
    return self._preview_early_exit()


@external
@nonreentrant
def complete():
    """
    @dev Free unlock: sends `principal` to the NFT owner and closes the goal.
    @notice Reverts if `principal < target`. Surplus above principal goes to treasury.
    """
    self._check_open()
    self._check_nft_owner()
    assert self.principal >= TARGET, "payday_goal: under target"

    owner: address = msg.sender
    amount: uint256 = self.principal
    surplus: uint256 = self._surplus()
    self.principal = empty(uint256)
    self.closed = True

    self._payout(owner, amount)
    if surplus != empty(uint256):
        self._payout(TREASURY, surplus)

    extcall IPaydayFactory(FACTORY).set_goal_uri_completed(TOKEN_ID)
    log Completed(owner=owner, amount=amount)


@external
@nonreentrant
def early_exit():
    """
    @dev All-or-nothing exit while `principal < target`.
    @notice Fee (linear decaying bps) goes to treasury; net to the NFT owner.
            Closes the goal. Surplus above principal goes to treasury.
    """
    self._check_open()
    self._check_nft_owner()
    assert self.principal < TARGET, "payday_goal: use complete"

    owner: address = msg.sender
    fee: uint256 = empty(uint256)
    net: uint256 = empty(uint256)
    fee, net = self._preview_early_exit()
    penalty: uint256 = self._penalty_bps()
    surplus: uint256 = self._surplus()

    self.principal = empty(uint256)
    self.closed = True

    self._payout(TREASURY, fee)
    self._payout(owner, net)
    if surplus != empty(uint256):
        self._payout(TREASURY, surplus)

    extcall IPaydayFactory(FACTORY).set_goal_uri_completed(TOKEN_ID)
    log EarlyExit(owner=owner, fee=fee, net=net, penalty_bps=penalty)


@external
@nonreentrant
def skim_yield():
    """
    @dev Sends surplus above nominal `principal` to treasury.
    @notice Reverts on vault shortfall (NAV < principal). Anyone may call.
    """
    self._check_open()
    surplus: uint256 = self._surplus()
    assert surplus != empty(uint256), "payday_goal: no surplus"
    self._payout(TREASURY, surplus)
    log YieldSkimmed(surplus=surplus)


@internal
@view
def _check_open():
    """
    @dev Reverts if the goal has already been closed.
    """
    assert not self.closed, "payday_goal: closed"


@internal
@view
def _check_nft_owner():
    """
    @dev Reverts unless `msg.sender` currently owns the factory access NFT.
    """
    owner: address = staticcall IERC721(FACTORY).ownerOf(TOKEN_ID)
    assert msg.sender == owner, "payday_goal: caller is not nft owner"


@internal
@view
def _penalty_bps() -> uint256:
    """
    @dev `start_penalty_bps * (end_time - now) / (end_time - start_time)`
         while `now` is in `[start_time, end_time)`; full penalty before start;
         zero at/after end.
    @return uint256 Penalty in basis points.
    """
    now: uint256 = block.timestamp
    if now <= START_TIME:
        return START_PENALTY_BPS
    if now >= END_TIME:
        return empty(uint256)

    remaining: uint256 = END_TIME - now
    duration: uint256 = END_TIME - START_TIME
    return START_PENALTY_BPS * remaining // duration


@internal
@view
def _preview_early_exit() -> (uint256, uint256):
    """
    @dev `fee = principal * penalty_bps / 10_000` (round down), `net = principal - fee`.
    @return fee Treasury amount.
    @return net Owner amount.
    """
    bps: uint256 = self._penalty_bps()
    fee: uint256 = self.principal * bps // BPS_DENOMINATOR
    return fee, self.principal - fee


@internal
@view
def _held_assets() -> uint256:
    """
    @dev Assets controlled by this goal: ERC-20 balance, or vault NAV if set.
    @return uint256 Asset amount.
    """
    if VAULT == empty(address):
        return staticcall IERC20(ASSET).balanceOf(self)
    shares: uint256 = staticcall IERC20(VAULT).balanceOf(self)
    return staticcall IERC4626(VAULT).convertToAssets(shares)


@internal
@view
def _surplus() -> uint256:
    """
    @dev Held assets minus nominal principal. Reverts on vault shortfall.
    @return uint256 Surplus amount (may be zero).
    """
    held: uint256 = self._held_assets()
    assert held >= self.principal, "payday_goal: vault shortfall"
    return held - self.principal


@internal
@view
def _assert_vault_healthy():
    """
    @dev Blocks deposits when a configured vault's NAV is below principal.
    """
    if VAULT == empty(address):
        return
    held: uint256 = self._held_assets()
    assert held >= self.principal, "payday_goal: vault shortfall"


@internal
def _park(amount: uint256):
    """
    @dev Deposits `amount` of already-held assets into the vault when configured.
    @param amount Assets to park.
    """
    if VAULT == empty(address) or amount == empty(uint256):
        return
    success: bool = extcall IERC20(ASSET).approve(VAULT, amount)
    assert success, "payday_goal: vault approve failed"
    _: uint256 = extcall IERC4626(VAULT).deposit(amount, self)


@internal
def _payout(to: address, amount: uint256):
    """
    @dev Sends `amount` of `ASSET` to `to`, withdrawing from the vault if set.
    @param to Recipient.
    @param amount Asset amount. No-op when zero.
    """
    if amount == empty(uint256):
        return
    if VAULT == empty(address):
        success: bool = extcall IERC20(ASSET).transfer(to, amount)
        assert success, "payday_goal: transfer failed"
    else:
        _: uint256 = extcall IERC4626(VAULT).withdraw(amount, to, self)
