"""Source adapters against invented responses in each source's real shape (ADR-0003: never real responses)."""

import importlib
from datetime import date

import httpx
import pytest

from collector.discovery import discover_screens

discover_screens()
sources = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources")
yahoo = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources.yahoo")
finnhub = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources.finnhub")
nasdaq = importlib.import_module("trmnl_screens.bull-or-bear.collector.sources.nasdaq")

# 2026-11-23 and 2026-11-24 at 09:30 ET, and 16:00 / 16:30 ET on the 24th
MON, TUE, CLOSE, LATE = 1795444200, 1795530600, 1795554000, 1795555800


def chart(meta, timestamps, closes):
    return {"chart": {"result": [{"meta": meta, "timestamp": timestamps, "indicators": {"quote": [{"close": closes}]}}]}}


def yahoo_transport(seen=None, late_close=97.0):
    def handler(request):
        if seen is not None:
            seen.append(request)
        if request.url.params["interval"] == "1d":
            return httpx.Response(200, json=chart({"shortName": "Example Corp", "regularMarketPrice": 101.5,
                                                   "regularMarketTime": CLOSE}, [MON, TUE], [100.0, None]))
        meta = {"currentTradingPeriod": {"regular": {"start": TUE, "end": CLOSE}}}
        return httpx.Response(200, json=chart(meta, [TUE, CLOSE - 300, LATE], [100.5, 101.5, late_close]))
    return httpx.MockTransport(handler)


def test_yahoo_reads_closes_price_and_the_latest_after_hours_trade():
    seen = []
    q = yahoo.YahooSource(yahoo_transport(seen)).quote("EXMP")
    assert q == {"name": "Example Corp", "days": [["2026-11-23", 100.0]], "price": 101.5, "price_time": CLOSE,
                 "after": 97.0, "after_time": LATE}
    assert seen[0].url.path == "/v8/finance/chart/EXMP" and seen[0].headers["user-agent"] == "Mozilla/5.0"
    assert seen[1].url.params["includePrePost"] == "true"


def test_yahoo_has_no_after_hours_price_before_the_close():
    q = yahoo.YahooSource(yahoo_transport(late_close=None)).quote("EXMP")
    assert "after" not in q


def test_yahoo_refuses_anything_that_is_not_a_symbol():
    with pytest.raises(sources.SourceError):
        yahoo.YahooSource(yahoo_transport()).quote("../x")


def test_yahoo_errors_name_the_status_without_the_url():
    source = yahoo.YahooSource(httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(sources.SourceError) as e:
        source.quote("EXMP")
    assert str(e.value) == "Yahoo returned HTTP 429" and "yahoo.com" not in str(e.value)


def test_finnhub_reads_dates_and_time_of_day():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"earningsCalendar": [{"date": "2026-11-24", "hour": "amc", "symbol": "EXMP"},
                                                              {"date": "2027-02-20", "hour": None, "symbol": "EXMP"}]})

    got = finnhub.FinnhubSource("k3y", httpx.MockTransport(handler)).earnings("EXMP", date(2026, 11, 24))
    assert got == [{"date": "2026-11-24", "hour": "amc"}, {"date": "2027-02-20", "hour": ""}]
    assert seen[0].url.params["to"] == "2027-02-22" and seen[0].url.params["token"] == "k3y"


@pytest.mark.parametrize("key,status", [(None, 200), ("bad", 401)])
def test_finnhub_reports_a_missing_or_rejected_key_apart(key, status):
    source = finnhub.FinnhubSource(key, httpx.MockTransport(lambda r: httpx.Response(status, json={})))
    with pytest.raises(finnhub.FinnhubKeyError) as e:
        source.earnings("EXMP", date(2026, 11, 24))
    assert "bad" not in str(e.value)


def test_nasdaq_reads_pay_dates_and_skips_rows_it_cannot():
    body = {"data": {"dividends": {"rows": [
        {"exOrEffDate": "11/12/2026", "type": "Cash", "amount": "$0.27", "paymentDate": "11/16/2026"},
        {"exOrEffDate": "N/A", "type": "Cash", "amount": "N/A", "paymentDate": "N/A"}]}}}
    source = nasdaq.NasdaqSource(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    assert source.dividends("EXMP") == [{"pay": "2026-11-16", "amount": 0.27}]


def test_nasdaq_without_data_for_a_stock_has_no_dividends():
    source = nasdaq.NasdaqSource(httpx.MockTransport(lambda r: httpx.Response(200, json={"data": None})))
    assert source.dividends("EXMP") == []
