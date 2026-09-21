# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Mock ERC-4626
@custom:contract-name mock_erc4626
@license MIT
@author Payday
@notice 1:1 asset/share vault for Payday yield tests.
"""

from ethereum.ercs import IERC20

implements: IERC20

from ethereum.ercs import IERC20Detailed

implements: IERC20Detailed

from ethereum.ercs import IERC4626

implements: IERC4626

ASSET: public(immutable(address))

name: public(constant(String[32])) = "Mock Vault"

symbol: public(constant(String[8])) = "mvUSDC"

decimals: public(constant(uint8)) = 6

totalSupply: public(uint256)

balanceOf: public(HashMap[address, uint256])

allowance: public(HashMap[address, HashMap[address, uint256]])


event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256


event Deposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256


event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256


@deploy
@payable
def __init__(asset: address):
    """
    @dev Binds the vault to a single underlying ERC-20.
    @param asset Underlying asset.
    """
    assert asset != empty(address), "mock_erc4626: zero asset"
    ASSET = asset


@external
@view
def asset() -> address:
    """
    @dev Returns the underlying asset.
    @return address Asset token.
    """
    return ASSET


@external
@view
def totalAssets() -> uint256:
    """
    @dev Underlying balance held by the vault.
    @return uint256 Asset amount.
    """
    return staticcall IERC20(ASSET).balanceOf(self)


@external
@view
def convertToShares(assetAmount: uint256) -> uint256:
    """
    @dev Converts assets to shares using current NAV.
    @param assetAmount Assets.
    @return uint256 Shares.
    """
    return self._convert_to_shares(assetAmount)


@external
@view
def convertToAssets(shareAmount: uint256) -> uint256:
    """
    @dev Converts shares to assets using current NAV.
    @param shareAmount Shares.
    @return uint256 Assets.
    """
    return self._convert_to_assets(shareAmount)


@external
@view
def maxDeposit(owner: address) -> uint256:
    """
    @dev Unlimited deposits.
    @param owner Unused receiver hint.
    @return uint256 Max assets.
    """
    return max_value(uint256)


@external
@view
def previewDeposit(assets: uint256) -> uint256:
    """
    @dev Preview shares minted for `assets`.
    @param assets Assets.
    @return uint256 Shares.
    """
    return self._convert_to_shares(assets)


@external
def deposit(assets: uint256, receiver: address) -> uint256:
    """
    @dev Pulls `assets` from the caller and mints shares to `receiver`.
    @param assets Asset amount.
    @param receiver Share recipient.
    @return uint256 Shares minted.
    """
    shares: uint256 = self._convert_to_shares(assets)
    success: bool = extcall IERC20(ASSET).transferFrom(msg.sender, self, assets)
    assert success, "mock_erc4626: transferFrom failed"
    self.totalSupply += shares
    self.balanceOf[receiver] += shares
    log Deposit(sender=msg.sender, owner=receiver, assets=assets, shares=shares)
    log Transfer(sender=empty(address), receiver=receiver, value=shares)
    return shares


@external
@view
def maxMint(owner: address) -> uint256:
    """
    @dev Unlimited mint.
    @param owner Unused.
    @return uint256 Max shares.
    """
    return max_value(uint256)


@external
@view
def previewMint(shares: uint256) -> uint256:
    """
    @dev Preview assets required to mint `shares`.
    @param shares Shares.
    @return uint256 Assets.
    """
    return self._convert_to_assets(shares)


@external
def mint(shares: uint256, receiver: address) -> uint256:
    """
    @dev Mints `shares` by pulling the matching asset amount.
    @param shares Shares to mint.
    @param receiver Share recipient.
    @return uint256 Assets pulled.
    """
    assets: uint256 = self._convert_to_assets(shares)
    success: bool = extcall IERC20(ASSET).transferFrom(msg.sender, self, assets)
    assert success, "mock_erc4626: transferFrom failed"
    self.totalSupply += shares
    self.balanceOf[receiver] += shares
    log Deposit(sender=msg.sender, owner=receiver, assets=assets, shares=shares)
    log Transfer(sender=empty(address), receiver=receiver, value=shares)
    return assets


@external
@view
def maxWithdraw(owner: address) -> uint256:
    """
    @dev Assets withdrawable by `owner`.
    @param owner Share owner.
    @return uint256 Assets.
    """
    return self._convert_to_assets(self.balanceOf[owner])


@external
@view
def previewWithdraw(assets: uint256) -> uint256:
    """
    @dev Preview shares burned to withdraw `assets`.
    @param assets Assets.
    @return uint256 Shares.
    """
    return self._convert_to_shares(assets)


@external
def withdraw(assets: uint256, receiver: address, owner: address) -> uint256:
    """
    @dev Burns shares from `owner` and sends `assets` to `receiver`.
    @param assets Asset amount.
    @param receiver Asset recipient.
    @param owner Share owner.
    @return uint256 Shares burned.
    """
    shares: uint256 = self._convert_to_shares(assets)
    if owner != msg.sender:
        self.allowance[owner][msg.sender] -= shares
    self.balanceOf[owner] -= shares
    self.totalSupply -= shares
    success: bool = extcall IERC20(ASSET).transfer(receiver, assets)
    assert success, "mock_erc4626: transfer failed"
    log Transfer(sender=owner, receiver=empty(address), value=shares)
    log Withdraw(
        sender=msg.sender,
        receiver=receiver,
        owner=owner,
        assets=assets,
        shares=shares,
    )
    return shares


@external
@view
def maxRedeem(owner: address) -> uint256:
    """
    @dev Shares redeemable by `owner`.
    @param owner Share owner.
    @return uint256 Shares.
    """
    return self.balanceOf[owner]


@external
@view
def previewRedeem(shares: uint256) -> uint256:
    """
    @dev Preview assets returned when redeeming `shares`.
    @param shares Shares.
    @return uint256 Assets.
    """
    return self._convert_to_assets(shares)


@external
def redeem(shares: uint256, receiver: address, owner: address) -> uint256:
    """
    @dev Burns `shares` from `owner` and sends assets to `receiver`.
    @param shares Shares to burn.
    @param receiver Asset recipient.
    @param owner Share owner.
    @return uint256 Assets sent.
    """
    assets: uint256 = self._convert_to_assets(shares)
    if owner != msg.sender:
        self.allowance[owner][msg.sender] -= shares
    self.balanceOf[owner] -= shares
    self.totalSupply -= shares
    success: bool = extcall IERC20(ASSET).transfer(receiver, assets)
    assert success, "mock_erc4626: transfer failed"
    log Transfer(sender=owner, receiver=empty(address), value=shares)
    log Withdraw(
        sender=msg.sender,
        receiver=receiver,
        owner=owner,
        assets=assets,
        shares=shares,
    )
    return assets


@external
def transfer(to: address, amount: uint256) -> bool:
    """
    @dev Transfers vault shares.
    @param to Recipient.
    @param amount Shares.
    @return bool True on success.
    """
    self.balanceOf[msg.sender] -= amount
    self.balanceOf[to] += amount
    log Transfer(sender=msg.sender, receiver=to, value=amount)
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    """
    @dev Approves `spender` to move shares.
    @param spender Spender.
    @param amount Allowance.
    @return bool True on success.
    """
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)
    return True


@external
def transferFrom(owner: address, to: address, amount: uint256) -> bool:
    """
    @dev Transfers shares using allowance.
    @param owner Share owner.
    @param to Recipient.
    @param amount Shares.
    @return bool True on success.
    """
    self.allowance[owner][msg.sender] -= amount
    self.balanceOf[owner] -= amount
    self.balanceOf[to] += amount
    log Transfer(sender=owner, receiver=to, value=amount)
    return True


@external
def simulate_yield(amount: uint256):
    """
    @dev Testers donate `amount` of underlying from the caller to inflate NAV.
    @param amount Assets to donate.
    """
    success: bool = extcall IERC20(ASSET).transferFrom(msg.sender, self, amount)
    assert success, "mock_erc4626: yield transfer failed"


@external
def simulate_loss(amount: uint256):
    """
    @dev Burns `amount` of underlying held by the vault (NAV drop).
    @param amount Assets to destroy.
    """
    success: bool = extcall IERC20(ASSET).transfer(empty(address), amount)
    assert success, "mock_erc4626: loss transfer failed"


@internal
@view
def _total_assets() -> uint256:
    """
    @dev Underlying balance held by the vault.
    @return uint256 Asset amount.
    """
    return staticcall IERC20(ASSET).balanceOf(self)


@internal
@view
def _convert_to_shares(assets: uint256) -> uint256:
    """
    @dev Assets → shares. Empty vault mints 1:1.
    @param assets Asset amount.
    @return uint256 Shares.
    """
    supply: uint256 = self.totalSupply
    total_assets: uint256 = self._total_assets()
    if supply == empty(uint256) or total_assets == empty(uint256):
        return assets
    return assets * supply // total_assets


@internal
@view
def _convert_to_assets(shares: uint256) -> uint256:
    """
    @dev Shares → assets. Empty vault redeems 1:1.
    @param shares Share amount.
    @return uint256 Assets.
    """
    supply: uint256 = self.totalSupply
    if supply == empty(uint256):
        return shares
    return shares * self._total_assets() // supply
