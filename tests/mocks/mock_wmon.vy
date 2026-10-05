# pragma version ~=0.4.3
"""
@title Mock WMON
@custom:contract-name mock_wmon
@license GNU Affero General Public License v3.0 only
@author Payday
@notice Wrapped MON stand-in: name `Wrapped MON`, symbol `WMON`, 18 decimals.
@dev Sending MON (`deposit` or a plain transfer) mints WMON 1:1.
     `withdraw`, `burn`, and `burn_from` burn WMON and release the same
     amount of MON to the token holder. There is no unbacked `mint`.
"""

from ethereum.ercs import IERC20
implements: IERC20


from ethereum.ercs import IERC20Detailed
implements: IERC20Detailed


from snekmate.tokens.interfaces import IERC20Permit
implements: IERC20Permit


from snekmate.utils.interfaces import IERC5267
implements: IERC5267


from snekmate.auth import ownable as ow
initializes: ow


from snekmate.tokens import erc20
initializes: erc20[ownable := ow]


# `burn` / `burn_from` are redefined here so they release MON.
# snekmate `mint` stays internal-only so supply cannot outrun the MON balance.
exports: (
    erc20.name,
    erc20.symbol,
    erc20.decimals,
    erc20.totalSupply,
    erc20.balanceOf,
    erc20.allowance,
    erc20.nonces,
    erc20.owner,
    erc20.transfer,
    erc20.approve,
    erc20.transferFrom,
    erc20.permit,
    erc20.DOMAIN_SEPARATOR,
    erc20.eip712Domain,
    erc20.transfer_ownership,
    erc20.renounce_ownership,
)


# @dev Canonical Monad WMON metadata.
NAME: constant(String[25]) = "Wrapped MON"


# @dev Canonical Monad WMON symbol.
SYMBOL: constant(String[5]) = "WMON"


# @dev Canonical Monad WMON decimals. Matches native MON.
DECIMALS: constant(uint8) = 18


# @dev EIP-712 signing-domain version. Permit domains are versioned.
EIP712_VERSION: constant(String[20]) = "1"


# @dev Emitted when MON is locked and WMON is minted. Matches WETH9.
event Deposit:
    dst: indexed(address)
    wad: uint256


# @dev Emitted when WMON is burned and MON is released. Matches WETH9.
event Withdrawal:
    src: indexed(address)
    wad: uint256


@deploy
def __init__():
    """
    @dev Assigns ownership to `msg.sender`. Supply starts at zero and
         increases only when the contract receives MON.
    """
    ow.__init__()
    erc20.__init__(NAME, SYMBOL, DECIMALS, NAME, EIP712_VERSION)


@external
@payable
def deposit():
    """
    @dev Locks `msg.value` MON and mints the same amount of WMON to the caller.
    """
    self._deposit(msg.value)


@external
def withdraw(wad: uint256):
    """
    @dev Burns `wad` WMON from the caller and sends `wad` MON back.
    @param wad Amount of WMON to unwrap.
    """
    self._release(msg.sender, wad)


@external
def burn(amount: uint256):
    """
    @dev Burns `amount` WMON from the caller and releases the same amount of MON.
    @param amount Amount of WMON to burn.
    """
    self._release(msg.sender, amount)


@external
def burn_from(owner: address, amount: uint256):
    """
    @dev Burns `amount` WMON from `owner` using the caller's allowance and
         releases the MON to `owner`.
    @param owner Token holder whose WMON is burned.
    @param amount Amount of WMON to burn.
    """
    erc20._spend_allowance(owner, msg.sender, amount)
    self._release(owner, amount)


@external
@payable
def __default__():
    """
    @dev Plain MON transfers mint WMON the same way `deposit` does.
    """
    self._deposit(msg.value)


@internal
def _deposit(amount: uint256):
    """
    @dev Mints `amount` WMON to the caller. Backing is the MON just received.
    @param amount MON received with the call.
    """
    erc20._mint(msg.sender, amount)
    log Deposit(dst=msg.sender, wad=amount)


@internal
def _release(holder: address, amount: uint256):
    """
    @dev Burns `amount` from `holder`, then sends `amount` MON to `holder`.
         The stipend matches WETH `transfer` (2300 gas).
    @param holder Account whose WMON is burned and who receives the MON.
    @param amount Amount of WMON to unwrap.
    """
    erc20._burn(holder, amount)
    send(holder, amount, gas=2300)
    log Withdrawal(src=holder, wad=amount)
