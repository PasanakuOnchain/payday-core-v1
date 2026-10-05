# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Payday Factory
@custom:contract-name payday_factory
@license GNU Affero General Public License v3.0 only
@author Payday
@notice ERC-721 access pass factory for Payday savings goals.
@dev Deploys each `payday_goal` via `create_from_blueprint` and mints an
     NFT to the creator. `tokenURI` returns one of three immutable IPFS
     packs from the goal's `principal` and `closed` flag.
     Uses snekmate `ownable_2step` + `erc721`. NFT transfer moves goal
     control. Per-token `disable_transfers` is irreversible (soulbind).
"""


from ethereum.ercs import IERC165
from ethereum.ercs import IERC721
from snekmate.tokens.interfaces import IERC721Metadata
from snekmate.tokens.interfaces import IERC721Enumerable
from snekmate.auth import ownable as ow
from snekmate.auth import ownable_2step as o2
from snekmate.tokens import erc721


interface IGoalLifecycle:
    def principal() -> uint256: view
    def closed() -> bool: view


implements: IERC165
implements: IERC721
implements: IERC721Metadata
implements: IERC721Enumerable


initializes: ow
initializes: o2[ownable := ow]
initializes: erc721[ownable := ow]


# Mint / burn / minter / permit stay factory-controlled.
# Ownership is snekmate `ownable_2step`, not ERC-721's one-step transfer.
# Wrapped `transferFrom` and `safeTransferFrom` enforce soulbind.
exports: (
    erc721.name,
    erc721.symbol,
    erc721.balanceOf,
    erc721.ownerOf,
    erc721.approve,
    erc721.getApproved,
    erc721.setApprovalForAll,
    erc721.isApprovedForAll,
    erc721.totalSupply,
    erc721.tokenByIndex,
    erc721.tokenOfOwnerByIndex,
    erc721.supportsInterface,
)


exports: o2.__interface__


# @dev Basis points denominator for `fee = principal * bps / BPS_DENOMINATOR`.
BPS_DENOMINATOR: public(constant(uint256)) = 10_000


# @dev Penalty in bps written onto every new goal at `start_time` (80%).
START_PENALTY_BPS: public(constant(uint256)) = 8_000


# @dev Number of seconds in one day; used to express duration caps.
DAY: public(constant(uint256)) = 86_400


# @dev Minimum `end_time - block.timestamp` for a new goal (30 days).
MIN_DURATION: public(constant(uint256)) = 30 * DAY


# @dev Maximum `end_time - block.timestamp` for a new goal (730 days).
MAX_DURATION: public(constant(uint256)) = 730 * DAY


# @dev ERC-721 collection name passed to snekmate `erc721.__init__`.
NAME: constant(String[25]) = "Payday Goal"


# @dev ERC-721 collection symbol. Snekmate caps this at 5 characters.
SYMBOL: constant(String[5]) = "PAYD"


# @dev EIP-712 signing-domain name passed to snekmate `erc721.__init__`.
EIP712_NAME: constant(String[50]) = "Payday Goal"


# @dev EIP-712 signing-domain version passed to snekmate `erc721.__init__`.
EIP712_VERSION: constant(String[20]) = "1"


# @dev EIP-5202 blueprint address used by `create_from_blueprint`.
GOAL_BLUEPRINT: public(immutable(address))


# @dev Pack returned by `tokenURI` while `principal == 0` and not closed.
# @notice Maximum length is 432 characters.
URI_CREATED: public(immutable(String[432]))


# @dev Pack returned by `tokenURI` while `principal > 0` and not closed.
URI_IN_PROGRESS: public(immutable(String[432]))


# @dev Pack returned by `tokenURI` once the linked goal is closed.
URI_COMPLETED: public(immutable(String[432]))


struct AssetConfig:
    allowed: bool
    min_target: uint256
    min_deposit: uint256


# @dev Recipient of early-exit fees for newly created goals.
# @notice Existing clones keep the treasury snapshotted at `create_goal`.
treasury: public(address)


# @dev Owner-managed ERC-20 allowlist plus per-asset min target / min deposit.
asset_config: public(HashMap[address, AssetConfig])


# @dev Mapping from minted `token_id` to the goal clone that token controls.
goals: public(HashMap[uint256, address])


# @dev Inverse mapping from goal clone address to its access-NFT `token_id`.
token_of: public(HashMap[address, uint256])


# @dev Irreversible soulbind flag. When `True`, transfers of `token_id` revert.
transfers_disabled: public(HashMap[uint256, bool])


# @dev Emitted when a goal clone is deployed and its access NFT is minted.
event GoalCreated:
    goal: indexed(address)
    token_id: indexed(uint256)
    creator: indexed(address)
    asset: address
    target: uint256
    start_time: uint256
    end_time: uint256
    start_penalty_bps: uint256


# @dev Emitted when the NFT owner irreversibly disables transfers of `token_id`.
event TransfersDisabled:
    token_id: indexed(uint256)
    owner: indexed(address)


# @dev Emitted when the owner updates an asset's allowlist status or dust floors.
event AssetAllowlistUpdated:
    asset: indexed(address)
    allowed: bool
    min_target: uint256
    min_deposit: uint256


# @dev Emitted when the factory treasury used by subsequent goals is changed.
event TreasuryUpdated:
    treasury: indexed(address)


@deploy
@payable
def __init__(
    goal_blueprint: address,
    treasury: address,
    uri_created: String[432],
    uri_in_progress: String[432],
    uri_completed: String[432],
):
    """
    @dev Assigns the owner to `msg.sender` and initialises snekmate ERC-721.
         The three metadata packs are immutable for the life of the factory.
    @param goal_blueprint EIP-5202 blueprint address for `payday_goal`.
    @param treasury Address that receives early-exit fees.
    @param uri_created Static metadata URI for newly created goals.
    @param uri_in_progress Static metadata URI after the first deposit.
    @param uri_completed Static metadata URI after complete or early exit.
    """
    assert goal_blueprint != empty(address)  # dev: payday_factory: zero blueprint
    assert treasury != empty(address)  # dev: payday_factory: zero treasury
    assert len(uri_created) != empty(uint256)  # dev: payday_factory: empty created uri
    assert len(uri_in_progress) != empty(uint256)  # dev: payday_factory: empty progress uri
    assert len(uri_completed) != empty(uint256)  # dev: payday_factory: empty completed uri

    ow.__init__()
    o2.__init__()
    erc721.__init__(NAME, SYMBOL, "", EIP712_NAME, EIP712_VERSION)

    GOAL_BLUEPRINT = goal_blueprint
    URI_CREATED = uri_created
    URI_IN_PROGRESS = uri_in_progress
    URI_COMPLETED = uri_completed
    self.treasury = treasury


@external
@nonreentrant
def create_goal(
    asset: address,
    target: uint256,
    end_time: uint256,
) -> (address, uint256):
    """
    @dev Deploys a goal clone from the blueprint and mints an access NFT.
    @notice The NFT owner alone may deposit, complete, or early-exit.
            Transferring the NFT transfers control of the goal.
            Early-exit penalty is always `START_PENALTY_BPS`; callers cannot choose it.
    @param asset Allowlisted ERC-20 used for this goal.
    @param target Principal required for a free `complete()`.
    @param end_time Unix timestamp when the penalty reaches zero.
    @return goal The deployed goal contract.
    @return token_id The minted ERC-721 token id.
    """
    config: AssetConfig = self.asset_config[asset]
    assert config.allowed  # dev: payday_factory: asset not allowed
    assert target >= config.min_target  # dev: payday_factory: target too low
    assert end_time > block.timestamp  # dev: payday_factory: end time not future

    duration: uint256 = end_time - block.timestamp
    assert duration >= MIN_DURATION  # dev: payday_factory: duration too short
    assert duration <= MAX_DURATION  # dev: payday_factory: duration too long

    token_id: uint256 = erc721._counter
    erc721._counter = token_id + 1
    start_time: uint256 = block.timestamp

    goal: address = create_from_blueprint(
        GOAL_BLUEPRINT,
        self,
        asset,
        self.treasury,
        target,
        start_time,
        end_time,
        START_PENALTY_BPS,
        token_id,
        config.min_deposit,
        salt=convert(token_id, bytes32),
    )
    assert goal != empty(
        address
    )  # dev: payday_factory: blueprint deploy failed

    self.goals[token_id] = goal
    self.token_of[goal] = token_id

    erc721._safe_mint(msg.sender, token_id, b"")

    log GoalCreated(
        goal=goal,
        token_id=token_id,
        creator=msg.sender,
        asset=asset,
        target=target,
        start_time=start_time,
        end_time=end_time,
        start_penalty_bps=START_PENALTY_BPS,
    )
    return goal, token_id


@external
def disable_transfers(token_id: uint256):
    """
    @dev Irreversibly soulbinds `token_id` so it can never be transferred.
    @notice Only the current NFT owner may call this. Approvals are cleared.
            Deposit / complete / early-exit still work for the fixed owner.
    @param token_id The token to soulbind.
    """
    owner: address = erc721._owner_of(token_id)
    assert owner == msg.sender  # dev: payday_factory: caller is not token owner
    assert not self.transfers_disabled[token_id]  # dev: payday_factory: transfers already disabled # nosplit

    self.transfers_disabled[token_id] = True
    erc721._approve(empty(address), token_id)
    log TransfersDisabled(token_id=token_id, owner=owner)


@external
@payable
def transferFrom(owner: address, to: address, token_id: uint256):
    """
    @dev Transfers `token_id` unless soulbound.
    @notice Declared `payable` to match EIP-721.
    @param owner Current owner (must match onchain owner).
    @param to Recipient.
    @param token_id Token to transfer.
    """
    self._check_transfers_enabled(token_id)
    assert erc721._is_approved_or_owner(msg.sender, token_id)  # dev: erc721: caller is not token owner or approved # nosplit
    erc721._transfer(owner, to, token_id)


@external
@payable
def safeTransferFrom(
    owner: address, to: address, token_id: uint256, data: Bytes[1_024] = b""
):
    """
    @dev Safe-transfers `token_id` unless soulbound.
    @notice Declared `payable` to match EIP-721. Default `data` provides both
            EIP-721 `safeTransferFrom` selectors.
    @param owner Current owner (must match onchain owner).
    @param to Recipient.
    @param token_id Token to transfer.
    @param data Optional receiver callback data.
    """
    self._check_transfers_enabled(token_id)
    assert erc721._is_approved_or_owner(
        msg.sender, token_id
    )  # dev: erc721: caller is not token owner or approved
    erc721._safe_transfer(owner, to, token_id, data)


@external
def set_asset_allowed(
    asset: address,
    allowed: bool,
    min_target: uint256,
    min_deposit: uint256,
):
    """
    @dev Owner-managed ERC-20 allowlist plus per-asset dust floors.
    @param asset Token to allow or revoke.
    @param allowed Whether `create_goal` may use `asset`.
    @param min_target Minimum `target` when `allowed` is True.
    @param min_deposit Minimum deposit size copied into new goals.
    """
    ow._check_owner()
    assert asset != empty(address)  # dev: payday_factory: zero asset
    if allowed:
        assert min_deposit != empty(uint256)  # dev: payday_factory: zero min deposit # nosplit
        assert (min_target >= min_deposit)  # dev: payday_factory: min target below min deposit # nosplit

    self.asset_config[asset] = AssetConfig(
        allowed=allowed,
        min_target=min_target,
        min_deposit=min_deposit,
    )
    log AssetAllowlistUpdated(
        asset=asset,
        allowed=allowed,
        min_target=min_target,
        min_deposit=min_deposit,
    )


@external
def set_treasury(treasury: address):
    """
    @dev Updates the treasury used by subsequently created goals.
    @param treasury New fee recipient. Must be nonzero.
    """
    ow._check_owner()
    assert treasury != empty(address)  # dev: payday_factory: zero treasury
    self.treasury = treasury
    log TreasuryUpdated(treasury=treasury)


@external
@view
def tokenURI(token_id: uint256) -> String[512]:
    """
    @dev Returns the lifecycle metadata pack for `token_id`.
    @notice Created when principal is zero, InProgress after a deposit,
            Completed once the goal is closed. Closed wins over a zero
            principal, because complete and early-exit clear principal.
    @param token_id The access NFT.
    @return String The immutable IPFS pack URI for the current state.
    """
    erc721._require_minted(token_id)
    goal: address = self.goals[token_id]
    if staticcall IGoalLifecycle(goal).closed():
        return URI_COMPLETED
    if staticcall IGoalLifecycle(goal).principal() != empty(uint256):
        return URI_IN_PROGRESS
    return URI_CREATED


@external
@view
def owner_of_goal(goal: address) -> address:
    """
    @dev Returns the NFT owner that currently controls `goal`.
    @param goal Goal contract address.
    @return address Current ERC-721 owner.
    """
    assert goal != empty(address)  # dev: payday_factory: zero goal
    token_id: uint256 = self.token_of[goal]
    assert self.goals[token_id] == goal  # dev: payday_factory: unknown goal
    return erc721._owner_of(token_id)


@external
@view
def is_goal(goal: address) -> bool:
    """
    @dev Returns True if `goal` was deployed by this factory.
    @param goal Candidate address.
    @return bool Whether `goal` is a registered clone.
    """
    if goal == empty(address):
        return False
    token_id: uint256 = self.token_of[goal]
    return self.goals[token_id] == goal


@internal
@view
def _check_transfers_enabled(token_id: uint256):
    """
    @dev Reverts if `token_id` has been soulbound.
    @param token_id Token to check.
    """
    assert not self.transfers_disabled[token_id]  # dev: payday_factory: transfers disabled # nosplit
