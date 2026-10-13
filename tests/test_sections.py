from datetime import datetime, timedelta, timezone

from collector.sections import Section, collect_sections

EASTERN = timezone(timedelta(hours=-4))
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=EASTERN)
LATER = NOW + timedelta(minutes=15)
AIRING = {"stale": False, "items": [{"series": "Night Market"}]}


class SourceDown(Exception):
    pass


def ok(data):
    return lambda: data


def down():
    raise SourceDown("Sonarr returned HTTP 503")


def run(tmp_path, now=NOW, **builds):
    sections = {name: Section(source="sonarr", build=build) for name, build in builds.items()}
    return collect_sections(sections, tmp_path / "media.json", now)


def test_healthy_sections_pass_through_with_no_errors(tmp_path):
    assert run(tmp_path, airing=ok(AIRING)) == {"errors": [], "airing": AIRING}


def test_an_empty_section_is_left_out(tmp_path):
    assert run(tmp_path, airing=ok(None)) == {"errors": []}


def test_first_failure_with_no_prior_data_reports_the_error_and_leaves_the_section_out(tmp_path):
    assert run(tmp_path, airing=down) == {
        "errors": [{"source": "sonarr", "since": "2026-10-12T14:30:00-04:00"}],
    }


def test_a_failure_reuses_the_last_good_data_marked_stale(tmp_path):
    run(tmp_path, airing=ok(AIRING))
    result = run(tmp_path, now=LATER, airing=down)
    assert result["airing"] == {**AIRING, "stale": True}
    assert result["errors"] == [{"source": "sonarr", "since": "2026-10-12T14:45:00-04:00"}]


def test_since_stays_at_the_first_consecutive_failure(tmp_path):
    run(tmp_path, airing=down)
    result = run(tmp_path, now=LATER, airing=down)
    assert result["errors"] == [{"source": "sonarr", "since": "2026-10-12T14:30:00-04:00"}]


def test_recovery_clears_the_error_and_the_stale_flag(tmp_path):
    run(tmp_path, airing=ok(AIRING))
    run(tmp_path, now=LATER, airing=down)
    assert run(tmp_path, now=LATER + timedelta(minutes=15), airing=ok(AIRING)) == {"errors": [], "airing": AIRING}
    # A later failure starts a new run of failures.
    later = LATER + timedelta(minutes=30)
    assert run(tmp_path, now=later, airing=down)["errors"] == [{"source": "sonarr", "since": later.isoformat()}]


def test_an_emptied_section_is_not_brought_back_by_a_later_failure(tmp_path):
    run(tmp_path, airing=ok(AIRING))
    run(tmp_path, airing=ok(None))
    assert "airing" not in run(tmp_path, airing=down)


def test_one_failing_section_does_not_stop_the_others(tmp_path):
    sections = {
        "airing": Section(source="sonarr", build=down),
        "releasing_today": Section(source="radarr", build=ok({"stale": False, "items": [1]})),
    }
    result = collect_sections(sections, tmp_path / "media.json", NOW)
    assert result["releasing_today"] == {"stale": False, "items": [1]}
    assert [e["source"] for e in result["errors"]] == ["sonarr"]


def test_state_lives_in_the_file_so_it_survives_a_restart(tmp_path):
    # Each call reads the file afresh, exactly as a restarted process would.
    path = tmp_path / "volume" / "media.json"
    collect_sections({"airing": Section("sonarr", ok(AIRING))}, path, NOW)
    assert path.exists()
    result = collect_sections({"airing": Section("sonarr", down)}, path, LATER)
    assert result["airing"]["stale"] is True


def test_an_unreadable_state_file_starts_fresh(tmp_path):
    (tmp_path / "media.json").write_text("{not json")
    assert run(tmp_path, airing=ok(AIRING)) == {"errors": [], "airing": AIRING}


def test_the_failure_is_logged_without_a_traceback(tmp_path, caplog):
    run(tmp_path, airing=down)
    [record] = caplog.records
    assert "airing" in record.getMessage() and "Sonarr returned HTTP 503" in record.getMessage()
    assert record.exc_info is None
