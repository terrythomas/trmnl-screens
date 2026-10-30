# Where's My Stuff? Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Where's My Stuff? screen: a collector that reads Parcel and pushes labelled deliveries, and the approved Tickets template, on the X and the OG.

**Architecture:** A Parcel source adapter (`sources/parcel.py`) wraps HTTP. A pure rules module (`rules.py`) turns raw Parcel deliveries into stored records, then into the payload's shown deliveries and headline. The screen's `collect()` stores records through `collect_sections`, so stale data is relabelled on every run. The template is already written and approved; it only lays out what the collector sends.

**Tech Stack:** Python 3.12, httpx, pytest, Liquid (trmnlp preview, LaraPaper in production).

**Spec:** `docs/specs/wheres-my-stuff-screen.md`

## Mock-ups

The approved design, rendered from `screens/wheres-my-stuff/src/full.liquid` with the fixtures in `screens/wheres-my-stuff/fixtures/`, is in the private gallery artifact: https://claude.ai/artifact/EstXGFMJG7ezfvzgUqhZ46 (top section "Round 3 · step 4 of 4 · polish · final"; earlier rounds below it). Re-render locally with `scripts/preview-data wheres-my-stuff <fixture>.json` and `trmnlp serve` in `screens/wheres-my-stuff/`.

## Global Constraints

- Statuses: `stuck` (1, 6, 7), `delivered` (0), `out_for_delivery` (4), `ready_for_pickup` (3), `on_the_way` (2), `not_shipped` (5, 8); unknown codes → `on_the_way`.
- Action order: stuck, out_for_delivery, delivered, ready_for_pickup, on_the_way, not_shipped.
- Delivered stays 36 hours from its newest event's date, read in `TZ`; unparseable → kept.
- Copy is exact: "Today", "Tomorrow", "Wed", "Nov 12", "Yesterday 8:12 AM", "Delivered", "Today by 8 PM", "Pick up by Nov 6", "Waiting for you", "No estimate yet", "No update since Oct 24", "Missed delivery · Today", "Carrier problem · Today", "No updates yet", "Late · was Wed", "to pick up", "coming". The headline names every group; there is no fold. The separator is " · " (U+00B7).
- `INTERVAL_MINUTES = 15`. One deliveries request per run (Parcel allows 20 an hour).
- No URL, key or real Parcel response in any tracked file, error message or log line (ADR-0003). Real responses stay outside the repo.
- Never print `.env` values; the maintainer edits `.env`, not the agent.
- Every screen works on the X and the OG (AGENTS.md).

## Review Focus

1. **Parcel returns `{"success": false, "error_message": ...}` with HTTP 200** (bad key, rate limit): must raise `ParcelError`, so the screen goes stale instead of emptying. Test in Task 2.
2. **A rejected key**: 401/403 or no key must show "Parcel key rejected", not "Parcel down", because it never recovers alone. Tests in Tasks 2 and 5. What Parcel actually returns for a bad key is unverified; Task 6 checks it.
3. **A delivery missing every optional field** (only `status_code` and `tracking_number`): must produce a ticket with the tracking number as description and "No estimate yet". Test in Task 3.
4. **Midnight between runs while stale:** stored "today" deliveries must read "Yesterday" or Late on the next run. Test in Task 5.
5. **Event dates in an unexpected format** (e.g. "30 Oct 2026 22:27"): Delivered must stay shown, not crash or vanish. Test in Task 3.
6. **More than 8 deliveries that must be seen** (7 on the X under the banner): accepted limitation; the rest go into "+N more". No test; stated in CONTEXT and the spec.

---

### Task 1: Commit the approved design

**Files:**
- Add (already written): `screens/wheres-my-stuff/src/full.liquid`, `src/settings.yml`, `.trmnlp.yml`, `fixtures/*.json`, `docs/specs/wheres-my-stuff-screen.md`, this plan
- Modify (already written): `CONTEXT.md`
- Create: `screens/wheres-my-stuff/fixtures/sample.json` (a copy of `busy.json`)
- Modify: `.env.example`

- [ ] **Step 1:** Copy `fixtures/busy.json` to `fixtures/sample.json` so `scripts/preview-data` and the spec's contract have a default.
- [ ] **Step 2:** Add to `.env.example`, after the Game Time lines, with placeholders only:
  ```
  PARCEL_API_KEY=your-parcel-api-key
  WHERES_MY_STUFF_WEBHOOK_UUID=00000000-0000-0000-0000-000000000000
  WHERES_MY_STUFF_PLUGIN_ID=00000000-0000-0000-0000-000000000000
  ```
  and `# WHERES_MY_STUFF_INTERVAL_MINUTES=15` under the interval examples.
- [ ] **Step 3:** Run `gitleaks protect --staged` after staging (or let pre-commit run it). Expected: no leaks.
- [ ] **Step 4: Commit**
  ```bash
  git add CONTEXT.md .env.example docs/specs/wheres-my-stuff-screen.md docs/superpowers/plans/2026-10-30-wheres-my-stuff.md screens/wheres-my-stuff
  git commit -m "Where's My Stuff?: spec, plan and the approved Tickets template"
  ```

### Task 2: Parcel source adapter

**Files:**
- Create: `screens/wheres-my-stuff/collector/__init__.py` (temporary: just a docstring, so discovery can import the package; Task 5 fills it)
- Create: `screens/wheres-my-stuff/collector/sources/__init__.py` (empty)
- Create: `screens/wheres-my-stuff/collector/sources/parcel.py`
- Create: `screens/wheres-my-stuff/tests/recordings/parcel_recent.json`, `parcel_carriers.json`
- Test: `screens/wheres-my-stuff/tests/test_parcel_source.py`

**Interfaces:**
- Produces: `ParcelError(Exception)` (message never holds the URL or key); `ParcelKeyError(ParcelError)` with class attribute `source = "parcel-key"` (read by `collect_sections`); `ParcelSource(api_key: str, transport: httpx.BaseTransport | None = None)` with `.deliveries() -> list[dict]` (the raw `deliveries` array) and `.carriers() -> dict[str, str]` (code → name).

The recordings are **invented**, in Parcel's shape: `{"success": true, "deliveries": [...]}`, deliveries with `carrier_code`, `description`, `status_code`, `tracking_number`, `events` (`event`, `date` like "October 30, 2026 22:27", `location`), `date_expected` ("2026-11-04 12:00:00"), `date_expected_end`, `timestamp_expected_end` (epoch seconds). Include one delivery per status code 0–8, one with only `status_code` and `tracking_number`. `parcel_carriers.json` is a 5-entry subset in the real shape `{"ups": {"name": "UPS"}, ...}`.

- [ ] **Step 1: Write the failing tests**
  - `test_deliveries_asks_for_recent_with_the_key_header`: request is `GET api.parcel.app /external/deliveries/`, query `filter_mode=recent`, header `api-key == "test-key"`; returns the recording's list unchanged.
  - `test_carriers_maps_code_to_name`: `carriers()["ups"] == "UPS"`; request path `/external/supported_carriers.json`; no `api-key` header sent.
  - `test_unsuccessful_body_raises`: 200 with `{"success": false, "error_message": "Invalid API key"}` → `ParcelError`, message `"Parcel said: Invalid API key"`.
  - `test_rejected_key_is_its_own_error`: 401 and 403 → `ParcelKeyError("Parcel rejected the API key")`, `e.source == "parcel-key"`.
  - `test_http_error_hides_url_and_key`: 500 → `ParcelError("Parcel returned HTTP 500")`; `httpx.ConnectError` → message `"Parcel request failed: ConnectError"`; `"test-key"` and `"api.parcel.app"` not in `str(e)`; `e.__cause__ is None`.
  - `test_unexpected_body_raises`: `[]` or `{"success": true}` → `ParcelError("Parcel returned an unexpected response")`.
  Use the F1 pattern: `discover_screens()`, `importlib.import_module("trmnl_screens.wheres-my-stuff.collector.sources.parcel")`, `httpx.MockTransport`.
- [ ] **Step 2:** Run `pytest screens/wheres-my-stuff/tests/test_parcel_source.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement `parcel.py` after `screens/f1/collector/sources/jolpica.py`: one `httpx.Client(base_url="https://api.parcel.app/external", timeout=30)`, the key sent per request on `deliveries()` only, the same three `except` branches with `from None`, plus the `success` check.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Where's My Stuff?: Parcel source adapter"`

### Task 3: Rules, from Parcel deliveries to stored records

**Files:**
- Create: `screens/wheres-my-stuff/collector/rules.py`
- Test: `screens/wheres-my-stuff/tests/test_rules.py`

**Interfaces:**
- Consumes: raw delivery dicts as in Task 2's recording.
- Produces:
  - `STATUS: dict[int, str]`, `ORDER: tuple[str, ...]`, `LABEL: dict[str, str]` (`"stuck": "Stuck"`, … `"not_shipped": "Not shipped yet"`)
  - `record(raw: dict, carriers: dict[str, str]) -> dict` → keys `status`, `code` (Parcel's `status_code`, so Stuck can say why), `description`, `carrier`, `tracking`, `event`, `location`, `expected` (ISO date or None), `expected_end` (ISO date or None), `by` (ISO datetime in local `TZ` or None), `last_event_at` (ISO datetime in local `TZ` or None). JSON-safe, because it is stored by `collect_sections`.

- [ ] **Step 1: Write the failing tests** (TZ fixed to America/New_York as in F1's `test_collect.py`)
  - `test_status_codes`: 0→delivered, 1/6/7→stuck, 2→on_the_way, 3→ready_for_pickup, 4→out_for_delivery, 5/8→not_shipped, 42→on_the_way.
  - `test_record_reads_dates`: `date_expected "2026-11-04 12:00:00"` → `expected "2026-11-04"`; `timestamp_expected_end` for 20:00 New York → `by "2026-10-30T20:00:00-04:00"`; newest event `"October 30, 2026 08:12"` → `last_event_at "2026-10-30T08:12:00-04:00"`.
  - `test_record_carrier_name_or_code`: `"ups"` → `"UPS"`; `"zz"` not in carriers → `"ZZ"`.
  - `test_record_minimal_delivery`: only `status_code` 2 and `tracking_number "TN1"` → `description "TN1"`, `carrier ""`, every optional key `None`.
  - `test_record_strips_emoji`: description "Socks 🧦 & sandals" → "Socks & sandals" (collapse the double space); "🧦" alone → falls back to the tracking number.
  - `test_record_unparseable_event_date`: `"30 Oct 2026 22:27"` → `last_event_at None`, event text kept.
  - `test_event_repeating_status_is_trimmed`: status delivered, event "Delivered, front door" → `"front door"`; "Out for delivery" on out_for_delivery → `None`; "DELIVERED - mailbox" → `"mailbox"`; "Departed facility" unchanged.
- [ ] **Step 2:** Run `pytest screens/wheres-my-stuff/tests/test_rules.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `record`. Parse event dates with `datetime.strptime(s, "%B %d, %Y %H:%M")`, then `.astimezone()` on the naive value (local `TZ`). The trim: if `event.lower().startswith(LABEL[status].lower())`, drop the label and then `lstrip(" ,.-–—:")`; empty → `None`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Where's My Stuff?: read Parcel deliveries into stored records"`

### Task 4: Rules, from stored records to the payload

**Files:**
- Modify: `screens/wheres-my-stuff/collector/rules.py`
- Test: `screens/wheres-my-stuff/tests/test_rules.py`

**Interfaces:**
- Consumes: `record` output (Task 3).
- Produces: `shown(records: list[dict], now: datetime) -> list[dict]` (payload deliveries in action order, filtered, labelled; keys `status`, `description`, `carrier`, `when`, and when present `event`, `location`, `tracking` for stuck only, `late: True`); `headline(deliveries: list[dict]) -> str`.

Use `NOW = 2026-10-30 09:41 America/New_York` (a Friday) in every test.

- [ ] **Step 1: Write the failing tests**
  - `test_day_words`: expected today → "Today"; Oct 31 → "Tomorrow"; Nov 4 → "Wed"; Nov 5 → "Thu" (6 days); Nov 6 → "Nov 6".
  - `test_when_by_status`: stuck code 1 with `last_event_at` Oct 24 → "No update since Oct 24"; code 6 at 07:50 today → "Missed delivery · Today"; code 6 yesterday → "Missed delivery · Yesterday"; code 7 on Oct 27 → "Carrier problem · Tue"; code 7 on Oct 20 → "Carrier problem · Oct 20"; stuck with no events → "No updates yet"; delivered at 08:12 today → "8:12 AM"; delivered yesterday 18:30 → "Yesterday 6:30 PM"; out_for_delivery `by` 20:00 → "Today by 8 PM", `by` 20:30 → "Today by 8:30 PM", no `by` → "Today"; ready_for_pickup `expected_end` Nov 6 → "Pick up by Nov 6", none → "Waiting for you"; on_the_way Nov 12 → "Nov 12", none → "No estimate yet".
  - `test_late`: on_the_way expected Oct 28 → `when "Late · was Wed"`, `late True`; expected Oct 20 → "Late · was Oct 20"; out_for_delivery with `by` yesterday 20:00 → "Late · was Thu", `late True`; out_for_delivery with no `by` or `expected` and newest event yesterday → "Late · was Thu"; not late → no `late` key.
  - `test_delivered_36_hours`: `last_event_at` = NOW − 36 h → shown; NOW − 36 h − 1 min → dropped; `None` → shown with when "Delivered".
  - `test_action_order`: shuffled records of every status come out stuck, out_for_delivery, delivered, ready_for_pickup, on_the_way, not_shipped; two on_the_way Nov 12 and Nov 4 → Nov 4 first; one with no estimate last; a Late one (Oct 28) before one due today.
  - `test_sub_line_fields`: stuck keeps `tracking`, others drop it; empty `event`/`location` keys are absent.
  - `test_headline`: [out_for_delivery, delivered, on_the_way] → "1 out for delivery · 1 delivered · 1 coming"; on_the_way + not_shipped → "2 coming"; ready_for_pickup → "1 to pick up"; stuck, 3 out_for_delivery, delivered, ready_for_pickup, 3 on_the_way, 2 not_shipped → "1 stuck · 3 out for delivery · 1 delivered · 1 to pick up · 5 coming" (all five groups, no fold); [] → "".
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `shown` and `headline`. Sort key: `(ORDER.index(status), due or date.max)`, where `due` is `today` when late, else the status's day: Out for delivery's `by` date, else `expected`, else `last_event_at` date; Delivered's `last_event_at` date, newest first (sort on the negated date); Stuck's `last_event_at` date, oldest first; the others' `expected`. Stable on ties. The headline:
  ```python
  PART = {"stuck": "stuck", "delivered": "delivered", "out_for_delivery": "out for delivery",
          "ready_for_pickup": "to pick up", "on_the_way": "coming", "not_shipped": "coming"}
  counts = Counter(PART[d["status"]] for d in deliveries)  # insertion order = action order
  return " · ".join(f"{n} {part}" for part, n in counts.items())
  ```- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Where's My Stuff?: action order, labels and headline"`

### Task 5: The screen's collect()

**Files:**
- Modify: `screens/wheres-my-stuff/collector/__init__.py`
- Test: `screens/wheres-my-stuff/tests/test_collect.py`

**Interfaces:**
- Consumes: `ParcelSource`, `ParcelError` (Task 2); `record`, `shown`, `headline` (Tasks 3–4); `collector.sections.Section`, `collect_sections`.
- Produces: `INTERVAL_MINUTES = 15`; `collect(now: datetime | None = None, source: ParcelSource | None = None) -> dict` returning `{"updated_at", "headline", "deliveries", "errors"}` plus `"stale": True` when the section is stale.

- [ ] **Step 1: Write the failing tests** (fake source object with `deliveries()` / `carriers()`; `STATE_DIR` = `tmp_path`)
  - `test_payload_matches_the_contract`: keys are exactly `updated_at, headline, deliveries, errors` (plus `stale` only in the stale tests); `updated_at == "2026-10-30T09:41:00-04:00"`; every delivery's keys ⊆ the contract's.
  - `test_every_fixture_matches_the_contract`: each `fixtures/*.json` has only contract keys, known statuses, statuses in action order, and an `errors[].source` of `parcel` or `parcel-key` (keeps hand-made fixtures honest).
  - `test_parcel_failure_goes_stale_and_relabels`: run 1 at NOW with an out_for_delivery due today; run 2 the next day at 09:41 with the source raising `ParcelError` → `stale True`, `errors == [{"source": "parcel", "since": <run 2 time>}]`, and the delivery's when is no longer "Today…" (the stored record is relabelled).
  - `test_no_deliveries`: `deliveries == []`, `headline == ""`, no `stale`.
  - `test_stale_with_nothing_left_has_no_stale_flag`: stored records hold only a Delivered from 40 h ago, Parcel then fails → `deliveries == []`, no `stale`, `errors[0]["source"] == "parcel"`.
  - `test_carrier_list_cached_and_optional`: carriers fetched once across two runs within a day; `carriers()` raising `ParcelError` → payload still built, carrier shown as its code in capitals, `errors == []`.
  - `test_missing_key_is_an_error_not_a_crash`: no `PARCEL_API_KEY` and no `source` → `errors[0]["source"] == "parcel-key"`.
- [ ] **Step 2:** Run `pytest screens/wheres-my-stuff/tests/test_collect.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `collect`, following `screens/f1/collector/__init__.py`: state in `STATE_DIR/wheres-my-stuff/deliveries.json` via one `Section("parcel", build)`; `build` returns `{"records": [...]}` or `None` when Parcel returns none. After `collect_sections`, call `shown(records, now)` and `headline(...)`, so stale records are relabelled. Carriers: cached in `STATE_DIR/wheres-my-stuff/carriers.json` with a fetch time, refetched after 24 h, failures logged with `log.warning` only.
- [ ] **Step 4:** Run the whole suite: `pytest`. Expected: PASS, including `tests/test_discovery.py` with the new screen.
- [ ] **Step 5:** Smoke-run against the real API without printing the key or the response: `PARCEL_API_KEY` is read from `.env` by python-dotenv; write the payload to the scratchpad and post it to the preview: `scripts/preview-data`-style post to `trmnlp`, render X and OG, look at both. Never copy the output into the repo.
- [ ] **Step 6: Commit** `git commit -m "Where's My Stuff?: collect Parcel deliveries every 15 minutes"`

### Task 6: Deploy and check on LaraPaper

**Files:** none tracked (`.env` belongs to the maintainer).

- [ ] **Step 1:** Open a PR from `feature/parcels` (ask the maintainer first; the maintainer merges).
- [ ] **Step 2:** After merge, run `scripts/deploy wheres-my-stuff`. It creates the plugin and prints its ID. Ask the maintainer to add `WHERES_MY_STUFF_PLUGIN_ID`, `WHERES_MY_STUFF_WEBHOOK_UUID` and `PARCEL_API_KEY` to the production `.env`, then restart the collector (non-destructive `docker compose up -d`).
- [ ] **Step 3:** Check the LaraPaper render of the X and the OG against the gallery: PHP Liquid has only been checked through trmnlp. Look for the error-banner weekday (string slice compare), `| escape`, and `TRMNL_SKIP_DISPLAY`.
- [ ] **Step 4:** Find what Parcel returns for a wrong key (HTTP status, or 200 with `success: false`), using a deliberately wrong key, never the real one in output. If it is 200, map its `error_message` to `ParcelKeyError` too.
- [ ] **Step 5:** Settle the spec's Open source checks with the real data (in the scratchpad only): does `recent` return Delivered deliveries; what does a Stuck one look like. Update the spec, delete that section, and record the outcome in memory.
