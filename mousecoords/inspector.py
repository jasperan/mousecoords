"""Safe screen inspection helpers for profile-driven automation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import resolve_template_path
from .vision import VisionEngine


def _point_payload(x: int, y: int) -> dict[str, int]:
    """Return a stable x/y payload."""
    return {"x": int(x), "y": int(y)}


def _bounds_payload(bounds: tuple[int, int, int, int]) -> dict[str, int]:
    """Return a stable rectangle payload."""
    x, y, width, height = bounds
    return {
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
    }


def inspect_profile(
    *,
    profile,
    profile_path: str | Path | None = None,
    vision: VisionEngine | None = None,
    confidence: float = 0.8,
    include_ocr: bool = False,
) -> dict[str, Any]:
    """Inspect the current screen against a profile without clicking."""
    source = str(profile_path) if profile_path else "builtin default profile"
    resolved_profile_path = Path(profile_path) if profile_path else None
    vision = vision or VisionEngine(color_tolerance=profile.color_tolerance)

    buttons: list[dict[str, Any]] = []
    ocr_payload: dict[str, Any] = {}

    for button in profile.buttons:
        entry: dict[str, Any] = {
            "name": button.name,
            "detector": "template" if button.template else "color",
            "detected": False,
            "click_point": _point_payload(button.x, button.y),
        }

        if button.template:
            entry["template"] = button.template
            resolved_template = resolve_template_path(button.template, resolved_profile_path)
            entry["resolved_template"] = (
                str(resolved_template) if resolved_template is not None else None
            )
            if resolved_template is None:
                entry["error"] = f"Missing template: {button.template}"
            else:
                try:
                    template = vision.load_template(str(resolved_template))
                    bounds = vision.find_on_screen(template, confidence=confidence)
                except Exception as exc:  # pragma: no cover - depends on image backends
                    entry["error"] = str(exc)
                else:
                    if bounds is not None:
                        x, y, width, height = bounds
                        entry["detected"] = True
                        entry["match_bounds"] = _bounds_payload(bounds)
                        entry["click_point"] = _point_payload(x + width // 2, y + height // 2)
        else:
            actual_color = vision.get_pixel_color(button.x, button.y)
            entry["expected_color"] = list(button.color)
            entry["actual_color"] = list(actual_color)
            entry["tolerance"] = int(profile.color_tolerance)
            entry["detected"] = vision.color_matches(actual_color, button.color)

        buttons.append(entry)

    if include_ocr:
        for name, region in profile.ocr_regions.items():
            text = vision.read_text(region)
            number = vision.read_number(region)
            ocr_payload[name] = {
                "region": list(region),
                "text": text,
                "number": number,
            }

    detected_count = sum(1 for button in buttons if button["detected"])
    return {
        "profile_name": profile.name,
        "source": source,
        "confidence": confidence,
        "button_count": len(buttons),
        "detected_count": detected_count,
        "ok": detected_count == len(buttons),
        "buttons": buttons,
        "ocr": ocr_payload,
    }
