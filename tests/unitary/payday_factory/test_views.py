"""Factory view helpers: is_goal, owner_of_goal, token counter."""

import boa

from tests.utils import create_goal

EMPTY = "0x0000000000000000000000000000000000000000"


def test_is_goal_false_for_zero_address(factory):
    assert factory.is_goal(EMPTY) is False


def test_is_goal_false_for_random_address(factory):
    random_addr = boa.env.generate_address("not_a_goal")
    assert factory.is_goal(random_addr) is False


def test_owner_of_goal_zero_address_reverts(factory):
    with boa.reverts(dev="payday_factory: zero goal"):
        factory.owner_of_goal(EMPTY)


def test_owner_of_goal_unknown_goal_reverts(factory):
    random_addr = boa.env.generate_address("unknown_goal")
    with boa.reverts(dev="payday_factory: unknown goal"):
        factory.owner_of_goal(random_addr)


def test_second_create_goal_mints_token_id_one(factory, asset, saver):
    _, first_id = create_goal(factory, asset, saver)
    _, second_id = create_goal(factory, asset, saver)

    assert first_id == 0
    assert second_id == 1
    assert factory.totalSupply() == 2
    assert factory.ownerOf(second_id) == saver
    assert factory.tokenByIndex(1) == second_id
