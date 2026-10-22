import base64
import importlib.util
import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

# Loaded by path: the logo store has no imports from the rest of the collector package.
_spec = importlib.util.spec_from_file_location(
    "game_time_logos", Path(__file__).resolve().parent.parent / "collector" / "logos.py"
)
logos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(logos)

NOW = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
URL = "https://img.example/team/aaa.png?token=SECRET"

# Every image below is invented here; no real logo or icon is used (ADR-0009).


def png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def shield() -> bytes:
    """A navy shield with a white field and a navy letter, in a canvas with wide transparent margins."""
    im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(100, 50), (300, 50), (300, 250), (200, 350), (100, 250)], fill=(20, 30, 90, 255))
    d.polygon([(120, 70), (280, 70), (280, 240), (200, 320), (120, 240)], fill=(255, 255, 255, 255))
    d.rectangle((170, 110, 230, 250), fill=(20, 30, 90, 255))
    return png(im)


def wordmark(color=(255, 255, 255, 255)) -> bytes:
    """Block letters on transparency, wider than tall like a channel mark."""
    im = Image.new("RGBA", (600, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(20, 560, 110):
        d.rectangle((x, 20, x + 80, 140), fill=color)
        d.rectangle((x + 25, 50, x + 55, 110), fill=(0, 0, 0, 0))
    return png(im)


def blob() -> bytes:
    """A mostly black badge with a faint mark inside."""
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 199, 199), radius=30, fill=(10, 10, 10, 255))
    d.rectangle((90, 90, 110, 110), fill=(40, 40, 40, 255))
    return png(im)


def gradient() -> bytes:
    """A badge shaded from black to near-white, with no flat areas."""
    im = Image.new("L", (256, 128))
    im.putdata([x for _ in range(128) for x in range(256)])
    return png(im)


SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 12">'
    b'<path d="M1 1h8v10H1zM12 1h11v4H12z"/></svg>'
)


def decode(uri: str) -> Image.Image:
    prefix = "data:image/png;base64,"
    assert uri.startswith(prefix)
    return Image.open(io.BytesIO(base64.b64decode(uri[len(prefix):])))


def store(tmp_path, images, **kw):
    calls = []

    def fetch(url):
        calls.append(url)
        return images[url] if isinstance(images, dict) else images

    s = logos.LogoStore(tmp_path / "logos", fetch=fetch, **kw)
    s.calls = calls
    return s


def test_logo_is_trimmed_fitted_and_eight_grays(tmp_path):
    gray = decode(store(tmp_path, shield()).logo("nfl-aaa", URL, NOW).gray)
    # The 201 x 301 shield fills a 200 px box once the margins are trimmed.
    assert gray.height == 200
    assert gray.width == round(201 * 200 / 301)
    assert len(gray.convert("L").getcolors()) <= 8
    assert gray.convert("L").getpixel((gray.width // 2, 5)) < 64


def test_icon_is_fitted_in_its_box(tmp_path):
    gray = decode(store(tmp_path, wordmark((200, 0, 0, 255))).icon("Channel A", URL, NOW).gray)
    assert gray.size == (240, round(121 * 240 / 521))


def test_white_art_is_drawn_black(tmp_path):
    gray = decode(store(tmp_path, wordmark()).icon("Channel A", URL, NOW).gray).convert("L")
    assert gray.getpixel((5, gray.height // 2)) < 64


def test_onebit_images_have_exact_heights(tmp_path):
    logo = store(tmp_path, shield()).logo("nfl-aaa", URL, NOW)
    icon = store(tmp_path, wordmark()).icon("Channel A", URL, NOW)
    for uri, height in [(logo.onebit, 32), (logo.onebit_big, 64), (icon.onebit, 20), (icon.onebit_big, 30)]:
        im = decode(uri)
        assert im.mode == "1"
        assert im.height == height


def test_mostly_black_logo_gets_no_onebit(tmp_path):
    logo = store(tmp_path, blob()).logo("nfl-aaa", URL, NOW)
    assert logo.gray
    assert logo.onebit is None and logo.onebit_big is None


def test_midtone_logo_gets_no_onebit(tmp_path):
    logo = store(tmp_path, gradient()).logo("nfl-aaa", URL, NOW)
    assert logo.gray
    assert logo.onebit is None and logo.onebit_big is None


def test_override_fixes_threshold(tmp_path):
    logo = store(tmp_path, gradient(), overrides={"nfl-aaa": 128}).logo("nfl-aaa", URL, NOW)
    im = decode(logo.onebit).convert("L")
    # Left half black, right half white: the fixed threshold wins over the mid-tone fallback.
    assert im.getpixel((2, 16)) == 0 and im.getpixel((im.width - 3, 16)) == 255


def test_override_forces_fallback(tmp_path):
    logo = store(tmp_path, shield(), overrides={"nfl-aaa": None}).logo("nfl-aaa", URL, NOW)
    assert logo.gray
    assert logo.onebit is None and logo.onebit_big is None


def test_svg_is_rasterised(tmp_path):
    icon = store(tmp_path, SVG).icon("Channel A", "https://cdn.example/icons/a.svg", NOW)
    assert decode(icon.gray).size == (211, 96)  # the 22 x 10 artwork, fitted by height
    assert decode(icon.onebit).height == 20


def test_cache_is_reused_for_a_week_then_refreshed(tmp_path):
    s = store(tmp_path, shield())
    first = s.logo("nfl-aaa", URL, NOW)
    assert s.logo("nfl-aaa", URL, NOW + timedelta(days=6)) == first
    assert len(s.calls) == 1

    # A new store (the next collector run) reads the same cache.
    again = store(tmp_path, shield())
    assert again.logo("nfl-aaa", URL, NOW + timedelta(days=6)) == first
    assert again.calls == []

    again.logo("nfl-aaa", URL, NOW + timedelta(days=8))
    assert len(again.calls) == 1


def test_changed_url_is_fetched_again(tmp_path):
    other = "https://img.example/team/aaa-new.png"
    s = store(tmp_path, {URL: shield(), other: blob()})
    s.logo("nfl-aaa", URL, NOW)
    assert s.logo("nfl-aaa", other, NOW).onebit is None
    assert s.calls == [URL, other]


def test_failed_fetch_returns_nothing_and_hides_url(tmp_path, caplog):
    def fetch(url):
        raise httpx.ConnectError(f"cannot reach {url}")

    with caplog.at_level(logging.WARNING):
        assert logos.LogoStore(tmp_path, fetch=fetch).logo("nfl-aaa", URL, NOW) is None
    assert "nfl-aaa" in caplog.text
    assert "SECRET" not in caplog.text and "img.example" not in caplog.text


def test_unreadable_image_returns_nothing(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert store(tmp_path, b"<html>not an image</html>").logo("nfl-aaa", URL, NOW) is None
    assert "nfl-aaa" in caplog.text


def test_failed_refresh_keeps_last_good_images(tmp_path):
    first = store(tmp_path, shield()).logo("nfl-aaa", URL, NOW)

    def fetch(url):
        raise httpx.ConnectError("down")

    later = logos.LogoStore(tmp_path / "logos", fetch=fetch).logo("nfl-aaa", URL, NOW + timedelta(days=8))
    assert later == first
