"""Temporary test for issue #14: a failing test must turn ci-gate red. Reverted right after."""


def test_ci_gate_turns_red_on_a_failing_test():
    assert 1 + 1 == 3
