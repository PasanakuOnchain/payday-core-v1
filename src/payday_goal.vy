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
"""


from ethereum.ercs import IERC20
from ethereum.ercs import IERC721


# @dev Basis points denominator for `fee = principal * bps / BPS_DENOMINATOR`.
BPS_DENOMINATOR: public(constant(uint256)) = 10_000


# @dev Factory ERC-721 that minted `TOKEN_ID` and authorises goal actions.
FACTORY: public(immutable(address))


# @dev ERC-20 held by this goal.
ASSET: public(immutable(address))


# @dev Recipient of early-exit fees for this clone.
TREASURY: public(immutable(address))


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


# @dev Nominal principal deposited by the NFT owner.
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


@deploy
@payable
def __init__(
    factory: address,
    asset: address,
    treasury: address,
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
    @param treasury Recipient of early-exit fees.
    @param target Principal required for a free complete.
    @param start_time Timestamp when the penalty curve starts.
    @param end_time Timestamp when the penalty reaches zero.
    @param start_penalty_bps Penalty in bps at `start_time`.
    @param token_id Factory ERC-721 token that gates this goal.
    @param min_deposit Minimum amount accepted by `deposit`.
    """
    assert factory != empty(address)  # dev: payday_goal: zero factory
    assert asset != empty(address)  # dev: payday_goal: zero asset
    assert treasury != empty(address)  # dev: payday_goal: zero treasury
    assert target != empty(uint256)  # dev: payday_goal: zero target
    assert end_time > start_time  # dev: payday_goal: bad times
    assert min_deposit != empty(uint256)  # dev: payday_goal: zero min deposit

    FACTORY = factory
    ASSET = asset
    TREASURY = treasury
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
    @notice The factory `tokenURI` switches to InProgress once `principal > 0`.
    @param amount Token amount; must be at least `MIN_DEPOSIT`.
    """
    self._check_open()
    self._check_nft_owner()
    assert amount >= MIN_DEPOSIT  # dev: payday_goal: amount below min

    success: bool = extcall IERC20(ASSET).transferFrom(msg.sender, self, amount)
    assert success  # dev: payday_goal: transferFrom failed

    self.principal += amount

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
    @notice Reverts if `principal < target`.
    """
    self._check_open()
    self._check_nft_owner()
    assert self.principal >= TARGET  # dev: payday_goal: under target

    owner: address = msg.sender
    amount: uint256 = self.principal
    self.principal = empty(uint256)
    self.closed = True

    self._payout(owner, amount)

    log Completed(owner=owner, amount=amount)


@external
@nonreentrant
def early_exit():
    """
    @dev All-or-nothing exit while `principal < target`.
    @notice Fee (linear decaying bps) goes to treasury; net to the NFT owner.
            Closes the goal.
    """
    self._check_open()
    self._check_nft_owner()
    assert self.principal < TARGET  # dev: payday_goal: use complete

    owner: address = msg.sender
    fee: uint256 = empty(uint256)
    net: uint256 = empty(uint256)
    fee, net = self._preview_early_exit()
    penalty: uint256 = self._penalty_bps()

    self.principal = empty(uint256)
    self.closed = True

    self._payout(TREASURY, fee)
    self._payout(owner, net)

    log EarlyExit(owner=owner, fee=fee, net=net, penalty_bps=penalty)


@internal
@view
def _check_open():
    """
    @dev Reverts if the goal has already been closed.
    """
    assert not self.closed  # dev: payday_goal: closed


@internal
@view
def _check_nft_owner():
    """
    @dev Reverts unless `msg.sender` currently owns the factory access NFT.
    """
    owner: address = staticcall IERC721(FACTORY).ownerOf(TOKEN_ID)
    assert msg.sender == owner  # dev: payday_goal: caller is not nft owner


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
def _payout(to: address, amount: uint256):
    """
    @dev Sends `amount` of `ASSET` to `to`.
    @param to Recipient.
    @param amount Asset amount. No-op when zero.
    """
    if amount == empty(uint256):
        return
    success: bool = extcall IERC20(ASSET).transfer(to, amount)
    assert success  # dev: payday_goal: transfer failed
