from tests.mocks import mock_usdc, mock_usdt0, mock_wmon


def moccasin_main():
    """Deploy mock USDC, USDT0, and WMON. The deployer is minter of the stables."""
    usdc = mock_usdc.deploy()
    usdt0 = mock_usdt0.deploy()
    wmon = mock_wmon.deploy()
    print("mock USDC:", usdc.address)
    print("mock USDT0:", usdt0.address)
    print("mock WMON:", wmon.address)
    return usdc, usdt0, wmon
