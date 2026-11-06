"""Weekly micro-habit plan: picking, daily check-offs, streaks, storage per pair."""

from datetime import date, timedelta

import pytest
from django.test import Client

from apps.compatibility import plan
from tests.test_flows import make_pair

FRI = date(2026, 11, 6)


def test_pick_keeps_known_titles_dedupes_and_caps_at_three():
    p = plan.pick({}, ["a", "x", "a", "b", "c", "d"], ["a", "b", "c", "d"], FRI)
    assert p["picked"] == ["a", "b", "c"] and p["started"] == "2026-11-06"


def test_toggle_marks_today_and_ignores_unpicked():
    p = plan.pick({}, ["a"], ["a", "b"], FRI)
    p = plan.toggle(p, "a", FRI)
    assert plan.state(p, FRI)["habits"][0]["today"] and plan.state(p, FRI)["week"][4]
    assert plan.toggle(p, "b", FRI) == p
    assert "done" in plan.toggle(p, "a", FRI) and not plan.toggle(p, "a", FRI)["done"]


def test_streak_counts_back_from_today_or_yesterday_and_breaks_on_a_gap():
    p = plan.pick({}, ["a"], ["a"], FRI)
    for days_ago in (1, 2, 4):
        p = plan.toggle(p, "a", FRI - timedelta(days=days_ago))
    assert plan.state(p, FRI)["streak"] == 2  # today not done yet, so it still counts from yesterday
    assert plan.state(plan.toggle(p, "a", FRI), FRI)["streak"] == 3


@pytest.mark.django_db
def test_demo_plan_lives_in_the_session():
    client = Client()
    title = client.get("/report/habits/").context["r"].habits[0].title
    assert client.post("/plan/pick/", {"habit": [title, "чужая"]}).json()["picked"] == [title]
    assert client.post("/plan/done/", {"habit": title}).json()["habits"][0]["today"]
    assert title in client.get("/daily/").content.decode()


@pytest.mark.django_db(transaction=True)
def test_stored_plan_is_saved_on_the_pair_and_only_for_its_owner():
    client = Client()
    stored = make_pair(client)
    title = client.get(f"/r/{stored.id}/habits/").context["r"].habits[1].title
    client.post("/plan/pick/", {"rid": stored.id, "habit": [title]})
    stored.pair.refresh_from_db()
    assert stored.pair.plan["picked"] == [title]
    assert Client().post("/plan/pick/", {"rid": stored.id, "habit": [title]}).status_code == 404
