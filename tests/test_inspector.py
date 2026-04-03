"""Tests for safe profile inspection helpers."""

from __future__ import annotations

from types import SimpleNamespace

from mousecoords.config import ButtonConfig, Profile
from mousecoords.inspector import inspect_profile


def test_inspect_profile_reports_color_matches():
    profile = Profile(
        name="demo",
        buttons=[ButtonConfig("Collect", 12, 34, (1, 2, 3), cooldown=0.1)],
        states=[],
        ocr_regions={"score": (0, 0, 10, 10)},
    )

    vision = SimpleNamespace(
        get_pixel_color=lambda x, y: (1, 2, 3),
        color_matches=lambda actual, expected: actual == expected,
        read_text=lambda region: "42",
        read_number=lambda region: 42.0,
    )

    payload = inspect_profile(profile=profile, vision=vision, include_ocr=True)

    assert payload["ok"] is True
    assert payload["detected_count"] == 1
    assert payload["buttons"][0]["actual_color"] == [1, 2, 3]
    assert payload["ocr"]["score"]["text"] == "42"
    assert payload["ocr"]["score"]["number"] == 42.0


def test_inspect_profile_reports_template_matches(tmp_path):
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("name: demo\n")
    template_path = tmp_path / "assets" / "collect.png"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_bytes(b"fake-image")

    profile = Profile(
        name="demo",
        buttons=[
            ButtonConfig(
                "Collect",
                0,
                0,
                (0, 0, 0),
                template="assets/collect.png",
                cooldown=0.1,
            )
        ],
        states=[],
    )

    vision = SimpleNamespace(
        load_template=lambda path: {"loaded": path},
        find_on_screen=lambda template, confidence=0.8: (10, 20, 30, 40),
    )

    payload = inspect_profile(
        profile=profile,
        profile_path=profile_path,
        vision=vision,
        confidence=0.92,
    )

    assert payload["confidence"] == 0.92
    assert payload["ok"] is True
    assert payload["buttons"][0]["detected"] is True
    assert payload["buttons"][0]["resolved_template"] == str(template_path)
    assert payload["buttons"][0]["match_bounds"] == {
        "x": 10,
        "y": 20,
        "width": 30,
        "height": 40,
    }
    assert payload["buttons"][0]["click_point"] == {"x": 25, "y": 40}
