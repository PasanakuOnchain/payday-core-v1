# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Mock USDC
@custom:contract-name mock_usdc
@license GNU Affero General Public License v3.0 only
@author Payday
@notice Monad USDC stand-in: name `USDC`, symbol `USDC`, 6 decimals.
@dev snekmate `erc20` reference wiring. The deployer is the owner.
     `mint` is open: any caller may create tokens.
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


# snekmate `mint` is minter-gated. This mock keeps the rest of the
# ERC-20 surface and replaces `mint` with an unrestricted entrypoint.
exports: (
    erc20.name,
    erc20.symbol,
    erc20.decimals,
    erc20.totalSupply,
    erc20.balanceOf,
    erc20.allowance,
    erc20.nonces,
    erc20.is_minter,
    erc20.owner,
    erc20.transfer,
    erc20.approve,
    erc20.transferFrom,
    erc20.burn,
    erc20.burn_from,
    erc20.set_minter,
    erc20.permit,
    erc20.DOMAIN_SEPARATOR,
    erc20.eip712Domain,
    erc20.transfer_ownership,
    erc20.renounce_ownership,
)


# @dev Canonical Monad USDC metadata.
NAME: constant(String[25]) = "USDC"


# @dev Canonical Monad USDC symbol. snekmate caps symbols at 5 characters.
SYMBOL: constant(String[5]) = "USDC"


# @dev Canonical Monad USDC decimals.
DECIMALS: constant(uint8) = 6


# @dev EIP-712 signing-domain version. Permit domains are versioned.
EIP712_VERSION: constant(String[20]) = "1"


@deploy
@payable
def __init__():
    """
    @dev Assigns ownership to `msg.sender`. Supply starts at zero.
         Anyone may call `mint`.
    """
    ow.__init__()
    erc20.__init__(NAME, SYMBOL, DECIMALS, NAME, EIP712_VERSION)


@external
def mint(owner: address, amount: uint256):
    """
    @dev Creates `amount` tokens and assigns them to `owner`.
         Any caller may mint. `owner` cannot be the zero address.
    @param owner Recipient.
    @param amount Amount to mint.
    """
    erc20._mint(owner, amount)
