"""The local API end to end (TestClient) over the fake bank: auth, flows, error mapping, privacy."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mono_it_tax.api.main import create_app
from mono_it_tax.config.constants.app import LAUNCH_TOKEN_HEADER
from tests.scenario.fake_bank import FakeBank, bank_item, kyiv_ts, make_settings, make_world
from tests.support import FakeClock, json_response

LAUNCH = "launch-token-for-tests"
AUTH = {LAUNCH_TOKEN_HEADER: LAUNCH}
SELECTION_M9 = {"year": 2026, "kind": "period", "period": "M9"}


def q3_bank() -> FakeBank:
    bank = FakeBank()
    bank.add("acc-1", bank_item("jul", kyiv_ts(2026, 7, 10), 100_000, description="З Білої картки"))
    bank.add(
        "acc-1",
        bank_item(
            "aug", kyiv_ts(2026, 8, 5), 250_000, counterName="ТОВ Ромашка", futureField="new"
        ),
    )
    bank.add("acc-1", bank_item("spend", kyiv_ts(2026, 8, 6), -5_000))
    return bank


def make_client(
    tmp_path: Path,
    bank: FakeBank | None = None,
    credential: str = "tok",
    web_dir: Path | None = None,
) -> TestClient:
    bank = bank or q3_bank()
    app = create_app(
        make_settings(tmp_path, credential),
        LAUNCH,
        make_world(tmp_path, bank, FakeClock()),
        web_dir,
        inline_jobs=True,
    )
    return TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False)


def post(client: TestClient, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, json=body, headers=AUTH)


def handles_of(client: TestClient) -> list[str]:
    response = client.get("/api/accounts", params={"year": 2026}, headers=AUTH)
    return [a["handle"] for a in response.json()]


def scope(client: TestClient, only_first: bool = True) -> dict[str, Any]:
    handles = handles_of(client)
    return {
        "selection": SELECTION_M9,
        "handles": handles[:1] if only_first else handles,
    }


def test_every_api_call_needs_the_launch_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/api/meta").status_code == 401
    assert client.get("/api/meta", headers={LAUNCH_TOKEN_HEADER: "wrong"}).status_code == 401
    assert client.get("/api/meta", headers=AUTH).status_code == 200


def test_other_hosts_are_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    foreign = TestClient(client.app, base_url="http://evil.example")
    assert foreign.get("/api/meta", headers=AUTH).status_code == 400


def test_static_ui_is_served_without_the_token(tmp_path: Path) -> None:
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<html>ui</html>", encoding="utf-8")
    client = make_client(tmp_path, web_dir=web)
    assert "ui" in client.get("/").text


def test_meta_reports_version_rules_and_store_key(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/api/meta", headers=AUTH).json()
    assert body["ready"] is True
    assert body["store_key"] == "keyring"
    assert body["years"] == [2026]
    assert body["current_year"] == 2026  # from the injected clock, in Kyiv time
    assert body["rules"]["version"].startswith("2026.")
    assert "linkedin.com" in body["rules"]["linkedin"]


def test_missing_token_blocks_with_the_how_to_guide(tmp_path: Path) -> None:
    client = make_client(tmp_path, credential="  ")
    meta = client.get("/api/meta", headers=AUTH).json()
    assert meta["ready"] is False
    assert meta["error"]["code"] == "config_token_missing"
    assert "api.monobank.ua" in meta["error"]["message"]
    blocked = client.get("/api/accounts", params={"year": 2026}, headers=AUTH)
    assert blocked.status_code == 503
    assert blocked.json()["code"] == "config_token_missing"


def test_accounts_expose_handles_and_masked_pans_but_never_ids(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/api/accounts", params={"year": 2026}, headers=AUTH)
    accounts = response.json()
    assert [a["currency"] for a in accounts] == ["UAH", "USD"]
    assert accounts[0]["masked_pans"] == ["5375********1111"]
    assert all(len(a["handle"]) == 10 for a in accounts)
    assert "acc-1" not in response.text
    assert handles_of(client) == [a["handle"] for a in accounts]  # stable handles


def test_account_with_several_cards_lists_every_masked_pan(tmp_path: Path) -> None:
    bank = q3_bank()
    bank.accounts[0]["maskedPan"] = ["537541******1111", "444111******2222"]
    client = make_client(tmp_path, bank)
    accounts = client.get("/api/accounts", params={"year": 2026}, headers=AUTH).json()
    assert accounts[0]["masked_pans"] == ["5375********1111", "4441********2222"]
    assert accounts[1]["masked_pans"] == []


def test_plan_counts_requests_and_time(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    plan = post(client, "/api/plan", scope(client, only_first=False)).json()
    assert plan["requests"] == 6
    assert plan["eta_seconds"] == 360.0
    assert {t["month"] for t in plan["tasks"]} == {"2026-07", "2026-08", "2026-09"}


def test_full_flow_fetch_mark_review_report(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = scope(client)
    job = post(client, "/api/fetch", body).json()
    assert (job["state"], job["done"], job["total"]) == ("done", 3, 3)
    assert client.get(f"/api/jobs/{job['id']}", headers=AUTH).json()["state"] == "done"

    listing = post(client, "/api/payments", body)
    assert "acc-1" not in listing.text  # no account ids in payment data either
    payments = {p["id"]: p for p in listing.json()["payments"]}
    assert set(payments) == {"jul", "aug"}  # incoming only
    assert payments["jul"]["possible_internal_transfer"] is True
    assert payments["aug"]["possible_internal_transfer"] is False
    assert payments["aug"]["counter_name"] == "ТОВ Ромашка"
    assert payments["aug"]["amount"] == "2500"
    assert payments["aug"]["extra"] == {"futureField": "new"}  # undecoded fields are kept
    assert all(m["state"] == "fetched" for m in listing.json()["months"])

    assert (
        post(
            client, "/api/marks", {"year": 2026, "payment_ids": ["aug"], "marked": True}
        ).status_code
        == 200
    )
    amount = post(
        client, "/api/marks/amount", {"year": 2026, "payment_id": "aug", "amount": "2000"}
    )
    assert amount.json() == {"amount": "2000"}

    blocked = post(client, "/api/report/info", body)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "months_not_reviewed"
    assert "2026-07" in blocked.json()["message"]

    review_body = {
        "year": 2026,
        "handles": body["handles"],
        "months": ["2026-07", "2026-08", "2026-09"],
    }
    states = post(client, "/api/review", review_body).json()
    assert {s["state"] for s in states} == {"reviewed"}
    assert [s["marked"] for s in states] == [0, 1, 0]

    info = post(client, "/api/report/info", body).json()
    assert info["income"] == "2000.00"
    assert info["single_tax"] == "100.00"
    assert "2 000.00" in info["text"]

    declaration = {
        "year": 2026,
        "period": "M9",
        "handles": body["handles"],
        "previous": {
            "income": "100000.00",
            "row_07": "0",
            "row_12": "5000.00",
            "row_23": "1000.00",
        },
    }
    result = post(client, "/api/report/declaration", declaration).json()
    assert result["rows"]["income"] == "102000.00"
    assert result["rows"]["row_14"] == "100.00"
    assert result["rows"]["row_25"] == "20.00"
    assert result["preliminary"] is False
    assert "102 000.00" in result["text"]
    assert result["declaration_due"] == "2026-11-09"
    esv = next(p for p in result["payments"] if p["tax"] == "esv")
    assert (esv["amount"], esv["due"]) == ("5707.02", "2026-10-19")

    again = post(client, "/api/report/declaration", {**declaration, "previous": None}).json()
    assert again["rows"] == result["rows"]  # the typed rows were stored; no need to type twice


def test_wrong_previous_rows_name_the_row(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = scope(client)
    post(client, "/api/fetch", body)
    review = {"year": 2026, "handles": body["handles"], "months": ["2026-07", "2026-08", "2026-09"]}
    post(client, "/api/review", review)
    bad = {
        "year": 2026,
        "period": "M9",
        "handles": body["handles"],
        "previous": {"income": "100000.00", "row_07": "0", "row_12": "1.00", "row_23": "1000.00"},
    }
    response = post(client, "/api/report/declaration", bad)
    assert response.status_code == 422
    assert response.json()["code"] == "decl_row_mismatch"
    assert "рядок 12" in response.json()["message"]


def test_reviewing_an_unfetched_month_is_a_clear_error(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = post(
        client,
        "/api/review",
        {"year": 2026, "handles": handles_of(client)[:1], "months": ["2026-07"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "month_not_fetched"


def test_unknown_things_are_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    unknown_handle = {"selection": SELECTION_M9, "handles": ["0123456789"]}
    assert post(client, "/api/plan", unknown_handle).status_code == 404
    mark = {"year": 2026, "payment_ids": ["ghost"], "marked": True}
    assert post(client, "/api/marks", mark).json()["code"] == "unknown_payment"
    assert client.get("/api/jobs/nope", headers=AUTH).json()["code"] == "job_not_found"


@pytest.mark.parametrize(
    ("selection", "code"),
    [
        ({"year": 2026, "kind": "months", "months": []}, "selection_empty"),
        (
            {"year": 2026, "kind": "months", "months": ["2025-12", "2026-01"]},
            "selection_multi_year",
        ),
    ],
)
def test_selection_errors_are_actionable(
    tmp_path: Path, selection: dict[str, Any], code: str
) -> None:
    client = make_client(tmp_path)
    response = post(
        client, "/api/plan", {"selection": selection, "handles": handles_of(client)[:1]}
    )
    assert response.status_code == 422
    assert response.json()["code"] == code


def test_malformed_requests_are_422(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    bad_month = {
        "selection": {"year": 2026, "kind": "months", "months": ["2026-13"]},
        "handles": [],
    }
    assert post(client, "/api/plan", bad_month).status_code == 422
    no_period = {"selection": {"year": 2026, "kind": "period"}, "handles": []}
    assert post(client, "/api/plan", no_period).status_code == 422


def test_bank_failures_become_a_failed_job_with_a_user_message(tmp_path: Path) -> None:
    bank = q3_bank()
    bank.statement_hook = lambda _n: json_response({"errorDescription": "bad"}, 403)
    client = make_client(tmp_path, bank)
    job = post(client, "/api/fetch", scope(client)).json()
    assert job["state"] == "failed"
    assert job["error"]["code"] == "token_rejected"
    assert "MONOBANK_TOKEN" in job["error"]["message"]


def test_unexpected_errors_are_generic_and_never_leak_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(tmp_path)
    body = scope(client)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("secret-internal-detail")

    monkeypatch.setattr("mono_it_tax.pipelines.fetch.FetchPipeline.prepare", boom)
    response = post(client, "/api/plan", body)
    assert response.status_code == 500
    assert response.json()["code"] == "internal"
    assert "secret-internal-detail" not in response.text
    job = post(client, "/api/fetch", body)
    assert job.status_code == 500


def test_my_data_lists_and_deletes_only_on_explicit_confirmation(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    post(client, "/api/fetch", scope(client))
    data = client.get("/api/data", headers=AUTH).json()
    assert [y["year"] for y in data["years"]] == [2026]
    assert data["years"][0]["bytes"] > 0
    assert data["key_storage"] == "keyring"
    assert client.delete("/api/data/2026", headers=AUTH).status_code == 400
    assert client.delete("/api/data", headers=AUTH).status_code == 400
    assert (
        client.delete("/api/data/2026", params={"confirm": True}, headers=AUTH).status_code == 200
    )
    assert client.get("/api/data", headers=AUTH).json()["years"] == []
    post(client, "/api/fetch", scope(client))
    assert client.delete("/api/data", params={"confirm": True}, headers=AUTH).json() == {
        "deleted_all": True
    }


def test_previous_request_text_names_the_rows_to_copy(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get(
        "/api/declaration/previous-request", params={"year": 2026, "period": "M9"}, headers=AUTH
    )
    text = response.json()["text"]
    assert "півріччя" in text
    for row in ("06", "07", "12", "23"):
        assert f"рядок {row}" in text
    first = client.get(
        "/api/declaration/previous-request", params={"year": 2026, "period": "Q1"}, headers=AUTH
    )
    assert "перша декларація" in first.json()["text"]


def test_bad_amounts_are_422_and_unmarked_payments_cannot_be_corrected(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = scope(client)
    post(client, "/api/fetch", body)
    amount = {"year": 2026, "payment_id": "aug", "amount": "2000"}
    assert (
        post(client, "/api/marks/amount", amount).json()["code"] == "unknown_payment"
    )  # not marked
    post(client, "/api/marks", {"year": 2026, "payment_ids": ["aug"], "marked": True})
    assert post(client, "/api/marks/amount", {**amount, "amount": "abc"}).status_code == 422
    assert post(client, "/api/marks/amount", {**amount, "amount": "-5"}).status_code == 422
    cleared = post(client, "/api/marks/amount", {**amount, "amount": None})
    assert cleared.json() == {"amount": None}
    unmarked = post(client, "/api/marks", {"year": 2026, "payment_ids": ["aug"], "marked": False})
    assert unmarked.json() == {"changed": 1}


def test_typed_previous_with_garbage_numbers_is_422(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = scope(client)
    post(client, "/api/fetch", body)
    declaration = {
        "year": 2026,
        "period": "M9",
        "handles": body["handles"],
        "previous": {"income": "x", "row_07": "0", "row_12": "0", "row_23": "0"},
    }
    assert post(client, "/api/report/declaration", declaration).status_code == 422
