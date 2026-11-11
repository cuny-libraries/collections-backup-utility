from datetime import date

import httpx
import pytest

from collections_backup import core


def test_month_key_formats_year_and_month():
    assert core.month_key(date(2026, 6, 13)) == "2026-06"


def test_sanitize_name_replaces_slashes_with_dots():
    assert core.sanitize_name("Art / Music") == "Art . Music"


def test_sanitize_name_leaves_plain_names_untouched():
    assert core.sanitize_name("Biology") == "Biology"


def test_collection_csv_path_builds_sanitized_path(tmp_path):
    path = core.collection_csv_path(tmp_path, "Hunter", "Art / Music", "991234")
    assert path == tmp_path / "Hunter" / "Art . Music-991234.csv"


NESTED_COLLECTIONS = {
    "collection": [
        {
            "name": "Parent",
            "mms_id": {"value": "P1"},
            "pid": {"link": "http://alma/P1"},
            "collection": [
                {
                    "name": "Child",
                    "mms_id": {"value": "C1"},
                    "pid": {"link": "http://alma/C1"},
                }
            ],
        },
        {"name": "NoPid", "mms_id": {"value": "N1"}},
    ]
}


def test_flatten_collections_returns_every_node_children_first():
    result = core.flatten_collections(NESTED_COLLECTIONS)
    assert result == [
        {"name": "Child", "mms_id": "C1", "pid_link": "http://alma/C1"},
        {"name": "Parent", "mms_id": "P1", "pid_link": "http://alma/P1"},
        {"name": "NoPid", "mms_id": "N1", "pid_link": None},
    ]


def test_flatten_collections_handles_missing_key():
    assert core.flatten_collections({}) == []


def test_mmsids_from_page_extracts_bib_ids():
    page = {"bib": [{"mms_id": "991"}, {"mms_id": "992"}]}
    assert core.mmsids_from_page(page) == ["991", "992"]


def test_mmsids_from_page_empty_when_no_bibs():
    assert core.mmsids_from_page({"total_record_count": 0}) == []


def _flaky_client(fail_times):
    """An httpx.Client whose transport raises ConnectError `fail_times` times,
    then returns 200. Records how many times it was called via `.calls`."""
    state = {"calls": 0}

    def handler(request):
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    client.calls = state  # type: ignore[attr-defined]
    return client


def test_get_with_retries_succeeds_after_transient_failures():
    client = _flaky_client(fail_times=2)
    response = core.get_with_retries(
        client, "http://alma/x", retries=3, sleep=lambda _s: None
    )
    assert response.status_code == 200
    assert client.calls["calls"] == 3  # 2 failures + 1 success


def test_get_with_retries_raises_after_exhausting_attempts():
    client = _flaky_client(fail_times=99)
    with pytest.raises(httpx.TransportError):
        core.get_with_retries(client, "http://alma/x", retries=3, sleep=lambda _s: None)
    assert client.calls["calls"] == 3  # gave up after `retries` attempts


# The Alma collections endpoint, and the query every /bibs page request uses.
ALMA = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections"
BIBS = "bibs?level=2&format=json&limit=100"


def _alma_handler(responses, requested):
    """A fake Alma server that answers only the exact URLs in `responses`.

    A value is sent as text if it's a str, or as JSON if it's a dict. Any other
    URL fails the test, so a wrong query parameter or a missing API key can't
    slip through. Each URL asked for is appended to `requested`.
    """

    def handler(request):
        url = str(request.url)
        requested.append(url)
        assert url in responses, f"unexpected request: {url}"
        body = responses[url]
        if isinstance(body, str):
            return httpx.Response(200, text=body)
        return httpx.Response(200, json=body)

    return handler


def _fake_alma(responses):
    """An httpx.Client wired to the fake Alma server (see `_alma_handler`).

    Records every requested URL, in order, in `.requested`.
    """
    requested = []
    handler = _alma_handler(responses, requested)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    client.requested = requested  # type: ignore[attr-defined]
    return client


def test_fetch_all_mmsids_paginates_until_empty_page():
    client = _fake_alma(
        {
            f"http://alma/coll/{BIBS}&apikey=KEY&offset=0": {
                "bib": [{"mms_id": "1"}, {"mms_id": "2"}]
            },
            f"http://alma/coll/{BIBS}&apikey=KEY&offset=100": {
                "bib": [{"mms_id": "3"}]
            },
            f"http://alma/coll/{BIBS}&apikey=KEY&offset=200": {},
        }
    )
    ids = core.fetch_all_mmsids(client, "http://alma/coll", "KEY")
    assert ids == ["1", "2", "3"]


def test_fetch_all_mmsids_returns_empty_without_pid_link():
    client = _fake_alma({})
    assert core.fetch_all_mmsids(client, None, "KEY") == []
    assert client.requested == []  # no network calls made


def test_write_csv_atomic_writes_header_and_ids(tmp_path):
    path = tmp_path / "Hunter" / "Bio-991.csv"
    core.write_csv_atomic(path, ["991", "992"])
    assert path.read_text() == "MMS ID\n991\n992\n"


def test_write_csv_atomic_leaves_no_temp_file(tmp_path):
    path = tmp_path / "Hunter" / "Bio-991.csv"
    core.write_csv_atomic(path, ["991"])
    leftovers = [p.name for p in path.parent.iterdir() if p.name != path.name]
    assert leftovers == []


COLLECTIONS_PAYLOAD = {
    "collection": [
        {"name": "Bio", "mms_id": {"value": "B1"}, "pid": {"link": "http://alma/B1"}},
        {"name": "Art", "mms_id": {"value": "A1"}, "pid": {"link": "http://alma/A1"}},
    ]
}
ALMA_RESPONSES = {
    f"{ALMA}?level=20&apikey=KEY": "<xml/>",
    f"{ALMA}?level=20&format=json&apikey=KEY": COLLECTIONS_PAYLOAD,
    f"http://alma/B1/{BIBS}&apikey=KEY&offset=0": {
        "bib": [{"mms_id": "B1-1"}, {"mms_id": "B1-2"}]
    },
    f"http://alma/B1/{BIBS}&apikey=KEY&offset=100": {},
    f"http://alma/A1/{BIBS}&apikey=KEY&offset=0": {"bib": [{"mms_id": "A1-1"}]},
    f"http://alma/A1/{BIBS}&apikey=KEY&offset=100": {},
}


def test_run_backs_up_all_collections_and_writes_markers(tmp_path):
    client = _fake_alma(ALMA_RESPONSES)
    core.run(client, {"Hunter": "KEY"}, date(2026, 6, 13), tmp_path)

    base = tmp_path / "2026-06" / "Hunter"
    assert (base / "Bio-B1.csv").read_text() == "MMS ID\nB1-1\nB1-2\n"
    assert (base / "Art-A1.csv").read_text() == "MMS ID\nA1-1\n"
    assert (base / "COLLECTIONS.xml").read_text() == "<xml/>"
    assert (base / "COMPLETE").exists()
    assert (tmp_path / "2026-06" / "COMPLETE").exists()


def test_run_resumes_without_refetching_existing_collections(tmp_path):
    base = tmp_path / "2026-06" / "Hunter"
    base.mkdir(parents=True)
    (base / "Bio-B1.csv").write_text("PRE-EXISTING\n")  # pretend Bio finished last run

    client = _fake_alma(ALMA_RESPONSES)
    core.run(client, {"Hunter": "KEY"}, date(2026, 6, 13), tmp_path)

    assert (base / "Bio-B1.csv").read_text() == "PRE-EXISTING\n"  # untouched
    assert client.requested == [
        f"{ALMA}?level=20&apikey=KEY",
        f"{ALMA}?level=20&format=json&apikey=KEY",
        f"http://alma/A1/{BIBS}&apikey=KEY&offset=0",
        f"http://alma/A1/{BIBS}&apikey=KEY&offset=100",
    ]  # Bio was not downloaded again
    assert (base / "Art-A1.csv").read_text() == "MMS ID\nA1-1\n"
    assert (tmp_path / "2026-06" / "COMPLETE").exists()


def test_run_is_a_noop_when_month_already_complete(tmp_path):
    month = tmp_path / "2026-06"
    month.mkdir(parents=True)
    (month / "COMPLETE").touch()

    client = _fake_alma({})
    core.run(client, {"Hunter": "KEY"}, date(2026, 6, 13), tmp_path)

    assert client.requested == []  # zero network activity


def test_run_reports_progress_via_log_callback(tmp_path):
    client = _fake_alma(ALMA_RESPONSES)
    logs = []
    core.run(client, {"Hunter": "KEY"}, date(2026, 6, 13), tmp_path, log=logs.append)

    assert any("Hunter" in m for m in logs)  # the college is announced
    assert any("Bio" in m for m in logs)  # a collection name appears
    assert any("done" in m.lower() and "Hunter" in m for m in logs)  # completion


def test_run_logs_skipped_collections_on_resume(tmp_path):
    base = tmp_path / "2026-06" / "Hunter"
    base.mkdir(parents=True)
    (base / "Bio-B1.csv").write_text("PRE-EXISTING\n")  # Bio already done last run

    client = _fake_alma(ALMA_RESPONSES)
    logs = []
    core.run(client, {"Hunter": "KEY"}, date(2026, 6, 13), tmp_path, log=logs.append)

    assert any("Bio" in m and "skip" in m.lower() for m in logs)
