"""The backend against the real upstream, including its awkward habits."""

import asyncio
import copy

import pytest

from tests.conftest import FAIL_AND_LAND, FAIL_NOT_LANDED

pytestmark = pytest.mark.anyio

WIDE_FIELDS = {"internal_code", "region", "description", "investment_usd_m", "latitude", "tags", "linked_companies"}


def edited(project: dict, **changes) -> dict:
    out = copy.deepcopy(project)
    out.update(changes)
    return out


async def test_list_and_get_are_narrow(env):
    listing = (await env.api.get("/api/projects")).json()
    assert len(listing) == 30
    assert set(listing[0]) == {"id", "name", "sector", "country", "stage", "key_dates_count"}
    project = await env.load()
    assert set(project) == {"id", "name", "sector", "country", "stage", "key_dates"}
    assert not WIDE_FIELDS & set(project)


async def test_unknown_project_is_404_and_bad_input_is_422(env):
    assert (await env.api.get("/api/projects/P-0000")).status_code == 404
    project = await env.load()
    assert (await env.save(project, edited(project, sector="nope"))).status_code == 422
    assert (await env.save(project, edited(project, name=""))).status_code == 422
    dup = edited(project, key_dates=project["key_dates"] + [dict(project["key_dates"][0])])
    assert (await env.save(project, dup)).status_code == 422


async def test_different_fields_by_two_people_both_survive(env):
    ana, ben = await env.load(), await env.load()  # both open the form on the same version
    assert (await env.save(ana, edited(ana, name="Edited by Ana"))).status_code == 200
    response = await env.save(ben, edited(ben, country="Peru"))
    assert response.status_code == 200
    assert response.json()["also_changed_by_others"] == ["name"]
    stored = await env.upstream_record()
    assert (stored["name"], stored["country"]) == ("Edited by Ana", "Peru")


async def test_same_field_conflicts_nothing_is_written_and_second_saver_decides(env):
    ana, ben = await env.load(), await env.load()
    await env.save(ana, edited(ana, stage="financing"))

    response = await env.save(ben, edited(ben, stage="cancelled", name="Ben rename"))
    assert response.status_code == 409
    body = response.json()
    assert [(c["key"], c["theirs"], c["mine"]) for c in body["conflicts"]] == [("stage", "financing", "cancelled")]
    stored = await env.upstream_record()
    assert (stored["stage"], stored["name"]) == ("financing", ana["name"])  # a conflict writes nothing, not even Ben's rename

    # Ben decides to keep his value: base becomes what he just learned is stored, edited is proposed + his choice.
    resolved = {**body["proposed"], "stage": "cancelled"}
    final = await env.save(body["current"], resolved)
    assert final.status_code == 200
    stored = await env.upstream_record()
    assert (stored["stage"], stored["name"]) == ("cancelled", "Ben rename")


async def test_resolution_is_not_a_blind_overwrite_if_the_value_moved_again(env):
    ana, ben = await env.load(), await env.load()
    await env.save(ana, edited(ana, stage="financing"))
    body = (await env.save(ben, edited(ben, stage="cancelled"))).json()
    await env.nightly_write(stage="operation")  # changes again while Ben is deciding
    again = await env.save(body["current"], {**body["proposed"], "stage": "cancelled"})
    assert again.status_code == 409
    assert (await env.upstream_record())["stage"] == "operation"


async def test_nightly_job_writing_straight_to_upstream_is_seen_not_overwritten(env):
    ben = await env.load()
    await env.nightly_write(country="Brazil")  # different field than Ben touches
    assert (await env.save(ben, edited(ben, name="Ben rename"))).status_code == 200
    stored = await env.upstream_record()
    assert (stored["country"], stored["name"]) == ("Brazil", "Ben rename")

    carol = await env.load()
    await env.nightly_write(name="Nightly name")
    assert (await env.save(carol, edited(carol, name="Carol name"))).status_code == 409


async def test_linked_companies_changed_upstream_are_preserved_by_a_save(env):
    ben = await env.load()
    companies = [{"name": "Nightly Import SA", "role": "owner"}]
    await env.nightly_write(linked_companies=companies)
    assert (await env.save(ben, edited(ben, name="Ben rename"))).status_code == 200
    assert (await env.upstream_record())["linked_companies"] == companies


async def test_key_dates_edited_by_two_people_on_different_milestones_both_survive(env):
    ana, ben = await env.load(), await env.load()
    assert len(ana["key_dates"]) >= 2
    a_dates = copy.deepcopy(ana["key_dates"])
    a_dates[0]["date"] = "2031-01-01"
    b_dates = copy.deepcopy(ben["key_dates"])
    b_dates[1]["date"] = "2032-02-02"
    assert (await env.save(ana, edited(ana, key_dates=a_dates))).status_code == 200
    assert (await env.save(ben, edited(ben, key_dates=b_dates))).status_code == 200
    stored = (await env.upstream_record())["key_dates"]
    assert stored[0]["date"] == "2031-01-01" and stored[1]["date"] == "2032-02-02"
    assert len(stored) == len(ana["key_dates"])  # the wholesale list replace lost nothing


async def test_same_key_date_conflicts(env):
    ana, ben = await env.load(), await env.load()
    a_dates, b_dates = copy.deepcopy(ana["key_dates"]), copy.deepcopy(ben["key_dates"])
    a_dates[0]["date"], b_dates[0]["date"] = "2031-01-01", "2033-03-03"
    await env.save(ana, edited(ana, key_dates=a_dates))
    response = await env.save(ben, edited(ben, key_dates=b_dates))
    assert response.status_code == 409
    assert response.json()["conflicts"][0]["key"] == f"key_dates:{ana['key_dates'][0]['label']}"


async def test_504_that_did_write_is_recognised_and_reported_as_saved(env):
    project = await env.load()
    env.rng.script(*FAIL_AND_LAND)
    response = await env.save(project, edited(project, name="Landed despite 504"))
    assert response.status_code == 200
    assert response.json()["project"]["name"] == "Landed despite 504"
    assert (await env.upstream_record())["name"] == "Landed despite 504"


async def test_504_that_did_not_write_is_retried_until_it_lands(env):
    project = await env.load()
    env.rng.script(*FAIL_NOT_LANDED, *FAIL_NOT_LANDED)  # two failures, then the default draw lets it through
    response = await env.save(project, edited(project, name="Third time lucky"))
    assert response.status_code == 200
    assert (await env.upstream_record())["name"] == "Third time lucky"


async def test_persistent_504s_end_in_a_clear_not_saved_answer(env):
    project = await env.load()
    env.rng.script(*FAIL_NOT_LANDED * 5)
    response = await env.save(project, edited(project, name="Never lands"))
    assert response.status_code == 503
    assert response.json()["code"] == "not_saved" and response.json()["saved"] == "no"
    assert (await env.upstream_record())["name"] == project["name"]


async def test_last_attempt_that_landed_is_found_by_the_verification_read(env):
    project = await env.load()
    env.rng.script(*FAIL_NOT_LANDED * 2, *FAIL_AND_LAND)  # attempts 1-2 do not land, attempt 3 lands but answers 504
    response = await env.save(project, edited(project, name="Landed on the last try"))
    assert response.status_code == 200
    assert (await env.upstream_record())["name"] == "Landed on the last try"


async def test_saving_with_no_changes_writes_nothing(env):
    project = await env.load()
    env.rng.script(0.1, 0.9)  # would 504 if a PUT were attempted; none must be
    response = await env.save(project, project)
    assert response.status_code == 200
    assert env.rng.queue == [0.1, 0.9]


async def test_concurrent_saves_on_one_instance_different_fields_both_survive(env):
    ana, ben = await env.load(), await env.load()
    first, second = await asyncio.gather(
        env.save(ana, edited(ana, name="Ana concurrent")),
        env.save(ben, edited(ben, country="Peru")),
    )
    assert first.status_code == second.status_code == 200
    stored = await env.upstream_record()
    assert (stored["name"], stored["country"]) == ("Ana concurrent", "Peru")


async def test_concurrent_saves_on_one_instance_same_field_exactly_one_wins_the_other_decides(env):
    ana, ben = await env.load(), await env.load()
    first, second = await asyncio.gather(
        env.save(ana, edited(ana, stage="financing")),
        env.save(ben, edited(ben, stage="cancelled")),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
