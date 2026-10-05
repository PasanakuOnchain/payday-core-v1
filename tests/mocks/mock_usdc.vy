# pragma version ~=0.4.3
# pragma nonreentrancy off
"""
@title Mock USDC
@custom:contract-name mock_usdc
@license GNU Affero General Public License v3.0 only
@author Payday
@notice Monad USDC stand-in: name `USDC`, symbol `USDC`, 6 decimals.
@dev snekmate `erc20` reference wiring. The deployer is the owner and
     the first minter. `mint` is minter-gated.
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
exports: erc20.__interface__


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
    @dev Assigns ownership and the minter role to `msg.sender`.
         Supply starts at zero; minters call `mint`.
    """
    ow.__init__()
    erc20.__init__(NAME, SYMBOL, DECIMALS, NAME, EIP712_VERSION)
