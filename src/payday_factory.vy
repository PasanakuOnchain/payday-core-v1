# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Payday Factory
@custom:contract-name payday_factory
@license GNU Affero General Public License v3.0 only
@author Payday
@notice ERC-721 access pass factory for Payday savings goals.
@dev Deploys each `payday_goal` via `create_from_blueprint`, mints an NFT to
     the creator, and switches `tokenURI` among static IPFS metadata packs.
     Uses snekmate `ownable` + `erc721`. NFT transfer moves goal control.
     Per-token `disable_transfers` is irreversible (soulbind).
"""


from ethereum.ercs import IERC165
from ethereum.ercs import IERC721
from snekmate.tokens.interfaces import IERC721Metadata
from snekmate.tokens.interfaces import IERC721Enumerable
from snekmate.auth import ownable as ow
from snekmate.tokens import erc721


implements: IERC165
implements: IERC721
implements: IERC721Metadata
implements: IERC721Enumerable


initializes: ow
initializes: erc721[ownable := ow]


# Transfer / mint / burn / minter / permit stay factory-controlled.
# Wrapped `transferFrom` and `safeTransferFrom` enforce soulbind.
exports: (
    erc721.owner,
    erc721.name,
    erc721.symbol,
    erc721.balanceOf,
    erc721.ownerOf,
    erc721.approve,
    erc721.getApproved,
    erc721.setApprovalForAll,
    erc721.isApprovedForAll,
    erc721.tokenURI,
    erc721.totalSupply,
    erc721.tokenByIndex,
    erc721.tokenOfOwnerByIndex,
    erc721.supportsInterface,
    erc721.transfer_ownership,
    erc721.renounce_ownership,
)


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


struct AssetConfig:
    allowed: bool
    min_target: uint256
    min_deposit: uint256


# @dev Recipient of early-exit fees and skimmed yield for newly created goals.
# @notice Existing clones keep the treasury snapshotted at `create_goal`.
treasury: public(address)


# @dev Full IPFS metadata pack URI written at mint (`principal == 0`).
# @notice Snekmate base URI is empty, so `tokenURI` returns this string only.
#         Maximum length is 432 characters (snekmate `_token_uris` bound).
uri_created: public(String[432])


# @dev Full IPFS metadata pack URI written on the first successful deposit.
uri_in_progress: public(String[432])


# @dev Full IPFS metadata pack URI written on `complete` or `early_exit`.
uri_completed: public(String[432])


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


# @dev Emitted when the three static IPFS metadata pack URIs are replaced.
event UrisUpdated:
    uri_created: String[432]
    uri_in_progress: String[432]
    uri_completed: String[432]


# @dev Emitted when a linked goal updates `tokenURI` to a lifecycle pack.
event GoalUriUpdated:
    token_id: indexed(uint256)
    uri: String[432]


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
    @dev Assigns the owner to `msg.sender` and initialises snekmate ERC-721
         with an empty base URI so each token stores a full IPFS pack URI.
    @param goal_blueprint EIP-5202 blueprint address for `payday_goal`.
    @param treasury Address that receives early-exit fees and skimmed yield.
    @param uri_created Static metadata URI for newly created goals.
    @param uri_in_progress Static metadata URI after the first deposit.
    @param uri_completed Static metadata URI after complete or early exit.
    """
    assert goal_blueprint != empty(
        address
    )  # dev: payday_factory: zero blueprint
    assert treasury != empty(address)  # dev: payday_factory: zero treasury
    assert len(uri_created) != empty(
        uint256
    )  # dev: payday_factory: empty created uri
    assert len(uri_in_progress) != empty(
        uint256
    )  # dev: payday_factory: empty progress uri
    assert len(uri_completed) != empty(
        uint256
    )  # dev: payday_factory: empty completed uri

    ow.__init__()
    # Empty base URI: `tokenURI` returns the per-token pack string only.
    erc721.__init__(NAME, SYMBOL, "", EIP712_NAME, EIP712_VERSION)

    GOAL_BLUEPRINT = goal_blueprint
    self.treasury = treasury
    self.uri_created = uri_created
    self.uri_in_progress = uri_in_progress
    self.uri_completed = uri_completed


@external
@nonreentrant
def create_goal(
    asset: address,
    target: uint256,
    end_time: uint256,
    vault: address = empty(address),
) -> (address, uint256):
    """
    @dev Deploys a goal clone from the blueprint and mints an access NFT.
    @notice The NFT owner alone may deposit, complete, or early-exit.
            Transferring the NFT transfers control of the goal.
            `vault` defaults to `empty(address)` (v1: no ERC-4626 parking).
            Early-exit penalty is always `START_PENALTY_BPS`; callers cannot choose it.
    @param asset Allowlisted ERC-20 used for this goal.
    @param target Principal required for a free `complete()`.
    @param end_time Unix timestamp when the penalty reaches zero.
    @param vault Optional IERC4626; empty disables yield.
    @return goal The deployed goal contract.
    @return token_id The minted ERC-721 token id.
    """
    config: AssetConfig = self.asset_config[asset]
    assert config.allowed  # dev: payday_factory: asset not allowed
    assert target >= config.min_target  # dev: payday_factory: target too low
    assert (
        end_time > block.timestamp
    )  # dev: payday_factory: end time not future

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
        vault,
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
    erc721._set_token_uri(token_id, self.uri_created)

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
    assert not self.transfers_disabled[
        token_id
    ]  # dev: payday_factory: transfers already disabled

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
    assert erc721._is_approved_or_owner(
        msg.sender, token_id
    )  # dev: erc721: caller is not token owner or approved
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
def set_goal_uri_in_progress(token_id: uint256):
    """
    @dev Sets the InProgress metadata pack. Callable only by the linked goal.
    @param token_id Token whose URI is updated.
    """
    self._check_goal_caller(token_id)
    erc721._set_token_uri(token_id, self.uri_in_progress)
    log GoalUriUpdated(token_id=token_id, uri=self.uri_in_progress)


@external
def set_goal_uri_completed(token_id: uint256):
    """
    @dev Sets the Completed metadata pack. Callable only by the linked goal.
    @param token_id Token whose URI is updated.
    """
    self._check_goal_caller(token_id)
    erc721._set_token_uri(token_id, self.uri_completed)
    log GoalUriUpdated(token_id=token_id, uri=self.uri_completed)


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
        assert min_deposit != empty(
            uint256
        )  # dev: payday_factory: zero min deposit
        assert (
            min_target >= min_deposit
        )  # dev: payday_factory: min target below min deposit

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
    @param treasury New fee / yield recipient. Must be nonzero.
    """
    ow._check_owner()
    assert treasury != empty(address)  # dev: payday_factory: zero treasury
    self.treasury = treasury
    log TreasuryUpdated(treasury=treasury)


@external
def set_uris(
    uri_created: String[432],
    uri_in_progress: String[432],
    uri_completed: String[432],
):
    """
    @dev Replaces the three static IPFS metadata packs for future transitions.
    @param uri_created Created-pack URI.
    @param uri_in_progress InProgress-pack URI.
    @param uri_completed Completed-pack URI.
    """
    ow._check_owner()
    assert len(uri_created) != empty(
        uint256
    )  # dev: payday_factory: empty created uri
    assert len(uri_in_progress) != empty(
        uint256
    )  # dev: payday_factory: empty progress uri
    assert len(uri_completed) != empty(
        uint256
    )  # dev: payday_factory: empty completed uri

    self.uri_created = uri_created
    self.uri_in_progress = uri_in_progress
    self.uri_completed = uri_completed
    log UrisUpdated(
        uri_created=uri_created,
        uri_in_progress=uri_in_progress,
        uri_completed=uri_completed,
    )


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
    assert not self.transfers_disabled[
        token_id
    ]  # dev: payday_factory: transfers disabled


@internal
@view
def _check_goal_caller(token_id: uint256):
    """
    @dev Reverts unless `msg.sender` is the goal cloned for `token_id`.
    @param token_id Token whose linked goal must be the caller.
    """
    goal: address = self.goals[token_id]
    assert goal != empty(address)  # dev: payday_factory: unknown token
    assert msg.sender == goal  # dev: payday_factory: caller is not goal
