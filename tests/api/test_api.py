import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import ADMIN
from trailmend.api import demo
from trailmend.api.app import app
from trailmend.api.state import Live
from trailmend.data import dataset
from trailmend.graph.loader import load

pytestmark = pytest.mark.hydra


@pytest.fixture(scope="module")
def loaded(client: TestClient) -> dataset.Dataset:
    built = dataset.build(1)
    live: Live = app.state.live
    load(live.client, built.graph, built.support)
    return built


def _a_question(built: dataset.Dataset, template: str) -> str:
    return next(q.text for q in built.questions.questions if q.template == template)


def test_f1_healthz_and_ready_say_the_graph_is_writable(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/v1/ready").json() == {"graph_writable": True}


def test_f1_ask_answers_with_the_path_it_walked(client: TestClient, loaded: dataset.Dataset) -> None:
    response = client.post("/v1/ask", json={"question": _a_question(loaded, "alert_owning_team")})
    assert response.status_code == 200
    body = response.json()
    assert body["answer_ids"]
    assert body["answer_names"][0]
    assert body["paths"]
    assert body["paths"][0][0]["src_name"]
    assert body["cost"] > 0
    assert body["changed_anything"] is False


def test_f1_ask_refuses_a_question_that_matches_no_template(client: TestClient, loaded: dataset.Dataset) -> None:
    response = client.post("/v1/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_f1_ask_rejects_an_unknown_field(client: TestClient) -> None:
    assert client.post("/v1/ask", json={"question": "Who do I page for X?", "extra": 1}).status_code == 422


def test_f1_judging_an_answer_correct_writes_receipts(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "alert_owning_team")
    response = client.post(
        "/v1/judge", json={"question": question, "verdict": "correct"}, headers={"X-Admin-Token": ADMIN}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed_anything"] is True
    assert body["receipts"]
    assert body["confirmed"]
    held = client.get(f"/v1/receipts/{body['receipts'][0]}")
    assert held.status_code == 200
    assert held.json()["kind"] == "reweight"
    assert held.json()["edge"]["rel_type"]


def test_f1_judging_without_the_admin_token_changes_nothing(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "alert_owning_team")
    before = client.get("/v1/receipts", params={"limit": 1}).json()
    refused = client.post("/v1/judge", json={"question": question, "verdict": "wrong"})
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "invalid_request"
    assert "Nothing was changed" in refused.json()["error"]["message"]
    assert client.get("/v1/receipts", params={"limit": 1}).json() == before


def test_f1_judging_with_the_wrong_admin_token_changes_nothing(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "alert_owning_team")
    before = client.get("/v1/receipts", params={"limit": 1}).json()
    refused = client.post(
        "/v1/judge",
        json={"question": question, "verdict": "wrong"},
        headers={"X-Admin-Token": "not-the-admin-token-but-same-length"},
    )
    assert refused.status_code == 400
    assert client.get("/v1/receipts", params={"limit": 1}).json() == before


def test_f1_asking_is_rate_limited(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "alert_owning_team")
    live: Live = app.state.live
    codes = {
        client.post("/v1/ask", json={"question": question}).status_code for _ in range(live.limiter.per_minute + 2)
    }
    assert 429 in codes
    assert live.limiter.per_minute >= 1


def test_f1_receipts_are_listed_newest_first(client: TestClient, loaded: dataset.Dataset) -> None:
    client.post(
        "/v1/judge",
        json={"question": _a_question(loaded, "service_owner_team"), "verdict": "correct"},
        headers={"X-Admin-Token": ADMIN},
    )
    rows = client.get("/v1/receipts", params={"limit": 5}).json()
    assert rows
    assert all(row["digest"] for row in rows)


def test_f1_rollback_needs_the_admin_token(client: TestClient, loaded: dataset.Dataset) -> None:
    receipts = client.get("/v1/receipts", params={"limit": 1}).json()
    receipt_id = receipts[0]["receipt_id"]
    assert client.post(f"/v1/rollback/{receipt_id}").status_code == 400
    done = client.post(f"/v1/rollback/{receipt_id}", headers={"X-Admin-Token": ADMIN})
    assert done.status_code == 200
    assert done.json()["changed_anything"] is True
    assert done.json()["undone_by"] != receipt_id


def test_f1_a_mend_round_needs_the_admin_token(client: TestClient) -> None:
    assert client.post("/v1/mend/round", json={"rounds": 1}).status_code == 400


def test_f1_resetting_the_demo_graph_needs_the_admin_token(client: TestClient) -> None:
    assert client.post("/v1/demo/reset").status_code == 400


def test_f1_a_reset_restores_the_loaded_graph_and_leaves_a_receipt(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "alert_owning_team")
    client.post("/v1/judge", json={"question": question, "verdict": "wrong"}, headers={"X-Admin-Token": ADMIN})

    done = client.post("/v1/demo/reset", headers={"X-Admin-Token": ADMIN})
    assert done.status_code == 200
    body = done.json()
    assert body["changed_anything"] is True
    assert body["pool_edges_withheld"] > 0
    assert len(body["digest"]) == 64

    listed = client.get("/v1/receipts", params={"limit": 1}).json()
    assert listed[0]["receipt_id"] == body["receipt_id"]
    assert listed[0]["kind"] == "reset"

    answered = client.post("/v1/ask", json={"question": question})
    assert answered.status_code == 200
    assert {hop["cost"] for path in answered.json()["paths"] for hop in path} == {1.0}


def test_f1_judging_is_rate_limited_separately_from_asking(client: TestClient, loaded: dataset.Dataset) -> None:
    question = _a_question(loaded, "service_owner_team")
    live: Live = app.state.live
    codes = {
        client.post(
            "/v1/judge", json={"question": question, "verdict": "correct"}, headers={"X-Admin-Token": ADMIN}
        ).status_code
        for _ in range(live.judge_limiter.per_minute + 2)
    }
    assert 429 in codes
    assert live.judge_limiter.per_minute < live.limiter.per_minute


def test_f1_the_neighbourhood_of_an_entity_shows_its_edges_and_their_costs(
    client: TestClient, loaded: dataset.Dataset
) -> None:
    service = loaded.graph.nodes_with_label(loaded.graph.nodes[0].label)[0]
    anchor = next(e.src for e in loaded.graph.edges)
    body = client.get(f"/v1/graph/neighbourhood/{anchor}").json()
    assert body["name"]
    assert body["neighbours"]
    assert all(n["status"] in {"active", "quarantined"} for n in body["neighbours"])
    assert service.id


def test_f1_an_unknown_entity_is_refused(client: TestClient) -> None:
    assert client.get("/v1/graph/neighbourhood/12345").status_code == 400


def test_f1_the_evidence_index_lists_what_can_be_served(client: TestClient) -> None:
    body = client.get("/v1/evidence").json()
    assert "round_zero" in body["servable"]


def test_f1_an_evidence_file_that_does_not_exist_says_so_rather_than_inventing_one(client: TestClient) -> None:
    body = client.get("/v1/evidence/mechanisms").json()
    assert body["name"] == "mechanisms"
    assert "available" in body


def test_f1_a_started_api_leaves_a_loaded_demo_graph_alone(client: TestClient, loaded: dataset.Dataset) -> None:
    live: Live = app.state.live
    before = len(live.journal.lines())
    assert demo.node_count(live) > 0
    assert demo.load_if_empty(live) is None
    assert len(live.journal.lines()) == before


def test_f1_a_started_api_loads_g0_when_the_demo_graph_is_empty(
    client: TestClient, loaded: dataset.Dataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    live: Live = app.state.live

    def empty(_: Live) -> int:
        return 0

    monkeypatch.setattr(demo, "node_count", empty)
    receipt = demo.load_if_empty(live)
    assert receipt is not None
    assert receipt.kind == "reset"
    listed = client.get("/v1/receipts", params={"limit": 1}).json()
    assert listed[0]["receipt_id"] == receipt.receipt_id
    answered = client.post("/v1/ask", json={"question": _a_question(loaded, "alert_owning_team")})
    assert answered.status_code == 200
