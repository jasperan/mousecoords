"""Debug bundle creation and inspection utilities."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from .config import profile_to_data
from .doctor import collect_diagnostics
from .screen import capture_screen


def capture_bundle_screenshot(output_dir: str | Path, name: str = "screen.png") -> Path | None:
    """Capture a screenshot for a debug bundle if the environment allows it."""
    output_path = Path(output_dir) / name
    try:
        image = capture_screen()
    except Exception:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def create_bundle(
    path: str | Path,
    manifest: dict,
    *,
    json_payloads: dict[str, object] | None = None,
    text_payloads: dict[str, str] | None = None,
    attachments: list[tuple[str, str | Path]] | None = None,
    profile_path: str | Path | None = None,
    profile_text: str | None = None,
    doctor_results: list[dict] | None = None,
    stats: dict | None = None,
    actions: list[dict] | None = None,
    screenshots: list[str | Path] | None = None,
) -> Path:
    """Create a zip bundle containing run metadata and optional artifacts."""
    bundle_path = Path(path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    enriched_manifest = dict(manifest)
    enriched_manifest.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    enriched_manifest.setdefault("bundle_version", 1)

    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(enriched_manifest, indent=2, sort_keys=True))

        if profile_path is not None:
            zf.write(profile_path, arcname="profile.yaml")
        elif profile_text is not None:
            zf.writestr("profile.yaml", profile_text)

        if doctor_results is not None:
            zf.writestr("doctor.json", json.dumps(doctor_results, indent=2, sort_keys=True))

        if stats is not None:
            zf.writestr("stats.json", json.dumps(stats, indent=2, sort_keys=True))

        if actions is not None:
            zf.writestr("actions.json", json.dumps(actions, indent=2, sort_keys=True))

        for name, payload in (json_payloads or {}).items():
            zf.writestr(name, json.dumps(payload, indent=2, sort_keys=True))

        for name, payload in (text_payloads or {}).items():
            zf.writestr(name, payload)

        for screenshot in screenshots or []:
            screenshot_path = Path(screenshot)
            if screenshot_path.exists():
                zf.write(screenshot_path, arcname=f"screenshots/{screenshot_path.name}")

        for arcname, attachment in attachments or []:
            attachment_path = Path(attachment)
            if attachment_path.exists():
                zf.write(attachment_path, arcname=arcname)

    return bundle_path


def inspect_bundle(path: str | Path) -> dict:
    """Return the manifest and file listing for a bundle."""
    bundle_path = Path(path)
    with ZipFile(bundle_path) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        return {
            "path": str(bundle_path),
            "manifest": manifest,
            "files": sorted(zf.namelist()),
        }


def collect_runtime_bundle_inputs(*, profile, result) -> dict:
    """Collect standard inputs for a debug bundle from a runtime result."""
    result_dict = result.to_dict() if hasattr(result, "to_dict") else {}
    actions = [
        action.to_dict() if hasattr(action, "to_dict") else action
        for action in getattr(result, "actions", [])
    ]
    manifest = {
        "profile": profile.name,
        "command": getattr(result, "command", "run"),
        "dry_run": result.dry_run,
        "final_phase": result.final_phase,
        "iterations": getattr(result, "iterations", 0),
        "error_count": len(result.errors),
    }
    doctor_results = [
        {
            "name": check.name,
            "passed": check.passed,
            "detail": check.detail,
            "required": check.required,
        }
        for check in collect_diagnostics()
    ]

    screenshot_dir = Path(tempfile.mkdtemp(prefix="mousecoords-bundle-"))
    screenshot = capture_bundle_screenshot(screenshot_dir)
    screenshots = [screenshot] if screenshot is not None else []

    return {
        "manifest": manifest,
        "profile_text": yaml.dump(profile_to_data(profile), default_flow_style=False, sort_keys=False),
        "doctor_results": doctor_results,
        "stats": result.stats,
        "actions": actions,
        "json_payloads": {"summary.json": result_dict} if result_dict else {},
        "screenshots": screenshots,
    }


def create_debug_bundle(*, bundle_dir: str | Path, inputs: dict) -> Path:
    """Create a timestamped debug bundle from collected runtime inputs."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_path = Path(bundle_dir) / f"run-{timestamp}.zip"
    return create_bundle(
        bundle_path,
        inputs["manifest"],
        profile_text=inputs.get("profile_text"),
        profile_path=inputs.get("profile_path"),
        doctor_results=inputs.get("doctor_results"),
        stats=inputs.get("stats"),
        actions=inputs.get("actions"),
        json_payloads=inputs.get("json_payloads"),
        text_payloads=inputs.get("text_payloads"),
        attachments=inputs.get("attachments"),
        screenshots=inputs.get("screenshots"),
    )
