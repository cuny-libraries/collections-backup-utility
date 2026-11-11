"""Tests for the entry point the systemd unit runs (`python -m collections_backup`)."""

from datetime import date

import httpx

from collections_backup import __main__ as cli

ALMA = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/collections"


class June13:
    """Stands in for `datetime.date` so main() thinks today is 2026-06-13."""

    @staticmethod
    def today():
        return date(2026, 6, 13)


def fake_network(transport, request):
    """Replaces httpx's real network call. Only these two URLs exist."""
    responses = {
        f"{ALMA}?level=20&apikey=HUNTER-KEY": httpx.Response(200, text="<xml/>"),
        f"{ALMA}?level=20&format=json&apikey=HUNTER-KEY": httpx.Response(
            200, json={"total_record_count": 0}
        ),
    }
    return responses[str(request.url)]


def test_main_backs_up_colleges_from_env_file_into_data_folder(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / ".env").write_text("Hunter=HUNTER-KEY\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "date", June13)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake_network)

    cli.main()

    month = tmp_path / "data" / "2026-06"
    assert (month / "Hunter" / "COLLECTIONS.xml").read_text() == "<xml/>"
    assert (month / "Hunter" / "COMPLETE").exists()
    assert (month / "COMPLETE").exists()
    assert "Hunter: done" in capsys.readouterr().out  # progress reaches the journal
