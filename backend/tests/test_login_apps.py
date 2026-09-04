"""One Discord redirect URI serving two frontends, with different entry rules.

The backoffice stays officers-only. The Pass War map admits any member of the
alliance guild and lets the token's is_admin decide who may save the shared
line-up — so the two apps must not be able to borrow each other's rules.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from dwsbot import security


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(jwt_secret="k" * 40)
    )


def test_state_round_trips_each_app():
    for app in security.APPS:
        assert security.verify_state(security.make_state(app)) == app


def test_unknown_app_falls_back_to_backoffice():
    # The stricter of the two, so a malformed hint cannot widen access.
    assert security.verify_state(security.make_state("evil")) == "backoffice"


def test_default_is_backoffice():
    assert security.verify_state(security.make_state()) == "backoffice"


def test_tampered_app_is_rejected():
    nonce, _app, issued, sig = security.make_state("backoffice").split(".")
    forged = f"{nonce}.passwar.{issued}.{sig}"
    assert security.verify_state(forged) is None


def test_garbage_and_old_states_are_rejected():
    assert security.verify_state("nope") is None
    assert security.verify_state("") is None
    stale = security.make_state("passwar")
    nonce, app, _issued, _sig = stale.split(".")
    old = str(int(time.time()) - 4000)
    assert security.verify_state(f"{nonce}.{app}.{old}.{_sig}") is None


@pytest.mark.parametrize(
    "app, is_admin, in_guild, expected",
    [
        ("backoffice", True, True, True),
        ("backoffice", False, True, False),    # plain member: no backoffice
        ("passwar", False, True, True),        # plain member: may read the plan
        ("passwar", True, True, True),
        ("passwar", False, False, False),      # outsider: nothing
        ("passwar", True, False, False),       # officer who left the guild
    ],
)
def test_entry_rule(app, is_admin, in_guild, expected):
    """Mirrors the rule in auth.callback: officers for the backoffice, guild
    membership for the map."""
    permitted = is_admin if app == "backoffice" else in_guild
    assert permitted is expected
