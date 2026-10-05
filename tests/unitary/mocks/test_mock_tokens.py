"""Mock USDC, USDT0, and WMON."""

import boa

from tests.mocks import mock_usdc, mock_usdt0, mock_wmon

MON = 10**18


def test_usdc_metadata_and_minter(owner):
    token = mock_usdc.deploy()
    assert token.name() == "USDC"
    assert token.symbol() == "USDC"
    assert token.decimals() == 6
    assert token.totalSupply() == 0
    assert token.owner() == owner
    assert token.is_minter(owner) is True


def test_usdt0_metadata():
    token = mock_usdt0.deploy()
    assert token.name() == "USDT0"
    assert token.symbol() == "USDT0"
    assert token.decimals() == 6
    assert token.totalSupply() == 0


def test_anyone_can_mint_usdc(saver):
    token = mock_usdc.deploy()
    token.mint(saver, 1_000_000, sender=saver)
    assert token.balanceOf(saver) == 1_000_000
    assert token.totalSupply() == 1_000_000


def test_anyone_can_mint_usdt0(saver):
    token = mock_usdt0.deploy()
    token.mint(saver, 1, sender=saver)
    assert token.balanceOf(saver) == 1
    assert token.totalSupply() == 1


def test_wmon_metadata():
    token = mock_wmon.deploy()
    assert token.name() == "Wrapped MON"
    assert token.symbol() == "WMON"
    assert token.decimals() == 18
    assert token.totalSupply() == 0


def test_deposit_mints_wmon(saver):
    boa.env.set_balance(saver, 2 * MON)
    token = mock_wmon.deploy()
    before = boa.env.get_balance(saver)

    token.deposit(value=MON, sender=saver)

    assert token.balanceOf(saver) == MON
    assert token.totalSupply() == MON
    assert boa.env.get_balance(token.address) == MON
    assert boa.env.get_balance(saver) == before - MON


def test_plain_mon_transfer_mints_wmon(saver):
    boa.env.set_balance(saver, 2 * MON)
    token = mock_wmon.deploy()

    boa.env.raw_call(token.address, sender=saver, value=MON)

    assert token.balanceOf(saver) == MON
    assert token.totalSupply() == MON
    assert boa.env.get_balance(token.address) == MON


def test_withdraw_releases_mon(saver):
    boa.env.set_balance(saver, 2 * MON)
    token = mock_wmon.deploy()
    token.deposit(value=MON, sender=saver)
    before = boa.env.get_balance(saver)

    token.withdraw(MON, sender=saver)

    assert token.balanceOf(saver) == 0
    assert token.totalSupply() == 0
    assert boa.env.get_balance(token.address) == 0
    assert boa.env.get_balance(saver) == before + MON


def test_burn_releases_mon(saver):
    boa.env.set_balance(saver, 2 * MON)
    token = mock_wmon.deploy()
    token.deposit(value=MON, sender=saver)
    before = boa.env.get_balance(saver)

    token.burn(MON // 2, sender=saver)

    assert token.balanceOf(saver) == MON // 2
    assert token.totalSupply() == MON // 2
    assert boa.env.get_balance(token.address) == MON // 2
    assert boa.env.get_balance(saver) == before + MON // 2


def test_burn_from_releases_mon_to_holder(saver, other):
    boa.env.set_balance(saver, 2 * MON)
    boa.env.set_balance(other, MON)
    token = mock_wmon.deploy()
    token.deposit(value=MON, sender=saver)
    token.approve(other, MON, sender=saver)
    holder_before = boa.env.get_balance(saver)
    spender_before = boa.env.get_balance(other)

    token.burn_from(saver, MON, sender=other)

    assert token.balanceOf(saver) == 0
    assert token.totalSupply() == 0
    assert boa.env.get_balance(saver) == holder_before + MON
    assert boa.env.get_balance(other) == spender_before
    assert boa.env.get_balance(token.address) == 0


def test_withdraw_above_balance_reverts(saver):
    boa.env.set_balance(saver, 2 * MON)
    token = mock_wmon.deploy()
    token.deposit(value=MON, sender=saver)

    with boa.reverts("erc20: burn amount exceeds balance"):
        token.withdraw(MON + 1, sender=saver)

    assert token.balanceOf(saver) == MON
    assert boa.env.get_balance(token.address) == MON
