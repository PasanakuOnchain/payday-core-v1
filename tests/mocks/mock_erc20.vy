# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Mock ERC-20
@custom:contract-name mock_erc20
@license MIT
@author Payday
@notice Minimal ERC-20 for Payday tests.
"""

from ethereum.ercs import IERC20

implements: IERC20

decimals: public(uint8)

name: public(String[32])

symbol: public(String[8])

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


@deploy
@payable
def __init__(name_: String[32], symbol_: String[8], decimals_: uint8):
    """
    @dev Sets token metadata. Supply starts at zero; tests call `mint`.
    @param name_ Token name.
    @param symbol_ Token symbol.
    @param decimals_ Token decimals.
    """
    self.name = name_
    self.symbol = symbol_
    self.decimals = decimals_


@external
def mint(to: address, amount: uint256):
    """
    @dev Unrestricted mint for tests.
    @param to Recipient.
    @param amount Amount to mint.
    """
    self.totalSupply += amount
    self.balanceOf[to] += amount
    log Transfer(sender=empty(address), receiver=to, value=amount)


@external
def burn(from_: address, amount: uint256):
    """
    @dev Unrestricted burn for simulating vault losses.
    @param from_ Account to burn from.
    @param amount Amount to burn.
    """
    self.balanceOf[from_] -= amount
    self.totalSupply -= amount
    log Transfer(sender=from_, receiver=empty(address), value=amount)


@external
def transfer(to: address, amount: uint256) -> bool:
    """
    @dev Transfers `amount` from the caller to `to`.
    @param to Recipient.
    @param amount Amount.
    @return bool True on success.
    """
    self.balanceOf[msg.sender] -= amount
    self.balanceOf[to] += amount
    log Transfer(sender=msg.sender, receiver=to, value=amount)
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    """
    @dev Sets `spender` allowance to `amount`.
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
    @dev Transfers `amount` from `owner` to `to` using allowance.
    @param owner Token owner.
    @param to Recipient.
    @param amount Amount.
    @return bool True on success.
    """
    self.allowance[owner][msg.sender] -= amount
    self.balanceOf[owner] -= amount
    self.balanceOf[to] += amount
    log Transfer(sender=owner, receiver=to, value=amount)
    return True
