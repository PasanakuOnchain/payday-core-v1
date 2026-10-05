"""Protocol constants shared by tests and deploy scripts."""

DAY = 86_400
MIN_DURATION = 30 * DAY
MAX_DURATION = 730 * DAY
START_PENALTY_BPS = 8_000
BPS_DENOMINATOR = 10_000

DECIMALS = 6
ONE = 10**DECIMALS
MIN_DEPOSIT = 1 * ONE
MIN_TARGET = 10 * ONE
DEFAULT_TARGET = 100 * ONE

URI_CREATED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_IN_PROGRESS = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"
URI_COMPLETED = "ipfs://bafybeif5rxra2mgl5tbke4nyqlnf5g6qcxgrmnxpcvk7jf5cv5ky3pojsq/default.png"

NAME = "Payday Goal"
SYMBOL = "PAYD"
