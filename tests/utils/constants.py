"""Protocol constants shared by tests and deploy scripts."""

DAY = 86_400
MIN_DURATION = 30 * DAY
MAX_DURATION = 730 * DAY
MAX_START_PENALTY_BPS = 5_000
DEFAULT_START_PENALTY_BPS = 2_000
BPS_DENOMINATOR = 10_000

DECIMALS = 6
ONE = 10**DECIMALS
MIN_DEPOSIT = 1 * ONE
MIN_TARGET = 10 * ONE
DEFAULT_TARGET = 100 * ONE

URI_CREATED = "ipfs://payday/v1/created.json"
URI_IN_PROGRESS = "ipfs://payday/v1/in-progress.json"
URI_COMPLETED = "ipfs://payday/v1/completed.json"

NAME = "Payday Goal"
SYMBOL = "PAYD"
