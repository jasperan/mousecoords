"""Minimal studio scaffolding helpers for profile-pack workflows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .config import Profile, resolve_profile_target, save_profile


@dataclass
class StudioProject:
    """Created studio scaffold paths and provenance."""

    output_dir: Path
    profile_path: Path
    source: str


def _blank_profile(name: str) -> Profile:
    """Create a minimal blank profile-pack starting point."""
    return Profile(name=name)


def create_studio_project(
    output_dir: str | Path,
    *,
    name: str | None = None,
    from_profile: str | None = None,
    force: bool = False,
) -> StudioProject:
    """Create a profile-pack scaffold for the next generation workflow."""
    output_path = Path(output_dir)
    profile_path = output_path / "profile.yaml"

    if output_path.exists():
        existing = [child for child in output_path.iterdir()]
        if existing and not force:
            raise FileExistsError(
                f"Directory '{output_path}' already exists and is not empty. Use --force to continue."
            )
    else:
        output_path.mkdir(parents=True, exist_ok=True)

    if from_profile:
        base_profile, _, source = resolve_profile_target(from_profile)
        profile = deepcopy(base_profile)
    else:
        source = "blank profile"
        profile = _blank_profile(name or output_path.name)

    profile.name = name or profile.name or output_path.name

    save_profile(profile, str(profile_path))

    for relative in ("assets/templates", "assets/reference"):
        directory = output_path / relative
        directory.mkdir(parents=True, exist_ok=True)
        keep = directory / ".gitkeep"
        keep.touch(exist_ok=True)

    return StudioProject(output_dir=output_path, profile_path=profile_path, source=source)
