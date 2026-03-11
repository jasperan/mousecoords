"""Configuration system with YAML profiles for resolution-independent automation."""

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class ButtonConfig:
    """Configuration for a single monitorable button."""
    name: str
    x: int
    y: int
    color: tuple
    action: str = "click"
    cooldown: float = 1.0
    template: Optional[str] = None  # path to template image for CV matching

    def __post_init__(self):
        if isinstance(self.color, list):
            self.color = tuple(self.color)


@dataclass
class StateConfig:
    """Configuration for a state machine state."""
    name: str
    monitor_buttons: list = field(default_factory=list)
    transitions: dict = field(default_factory=dict)
    max_actions: dict = field(default_factory=dict)


@dataclass
class Profile:
    """Complete automation profile for a game or application."""
    name: str
    game: str = ""
    resolution: tuple = (1920, 1080)
    poll_interval: float = 0.5
    color_tolerance: int = 3
    buttons: list = field(default_factory=list)
    states: list = field(default_factory=list)
    ocr_regions: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.resolution, list):
            self.resolution = tuple(self.resolution)

    def get_button(self, name: str) -> Optional[ButtonConfig]:
        """Look up a button by name."""
        for b in self.buttons:
            if b.name == name:
                return b
        return None

    def scale_to(self, target_w: int, target_h: int) -> Profile:
        """Return a new profile with coordinates scaled to a different resolution."""
        src_w, src_h = self.resolution
        sx = target_w / src_w
        sy = target_h / src_h

        scaled_buttons = []
        for b in self.buttons:
            scaled_buttons.append(ButtonConfig(
                name=b.name,
                x=int(b.x * sx),
                y=int(b.y * sy),
                color=b.color,
                action=b.action,
                cooldown=b.cooldown,
                template=b.template,
            ))

        scaled_ocr = {}
        for key, (rx, ry, rw, rh) in self.ocr_regions.items():
            scaled_ocr[key] = (int(rx * sx), int(ry * sy), int(rw * sx), int(rh * sy))

        return Profile(
            name=self.name,
            game=self.game,
            resolution=(target_w, target_h),
            poll_interval=self.poll_interval,
            color_tolerance=self.color_tolerance,
            buttons=scaled_buttons,
            states=self.states,  # states are resolution-independent
            ocr_regions=scaled_ocr,
        )


def load_profile(path: str) -> Profile:
    """Load a profile from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    buttons = [ButtonConfig(**b) for b in data.get("buttons", [])]
    states = [StateConfig(**s) for s in data.get("states", [])]

    # Convert ocr_regions values from lists to tuples
    ocr_regions = {}
    for key, val in data.get("ocr_regions", {}).items():
        ocr_regions[key] = tuple(val) if isinstance(val, list) else val

    return Profile(
        name=data["name"],
        game=data.get("game", ""),
        resolution=tuple(data.get("resolution", [1920, 1080])),
        poll_interval=data.get("poll_interval", 0.5),
        color_tolerance=data.get("color_tolerance", 3),
        buttons=buttons,
        states=states,
        ocr_regions=ocr_regions,
    )


def save_profile(profile: Profile, path: str):
    """Save a profile to a YAML file."""
    data = {
        "name": profile.name,
        "game": profile.game,
        "resolution": list(profile.resolution),
        "poll_interval": profile.poll_interval,
        "color_tolerance": profile.color_tolerance,
        "buttons": [
            {
                "name": b.name, "x": b.x, "y": b.y,
                "color": list(b.color), "action": b.action,
                "cooldown": b.cooldown,
                **({"template": b.template} if b.template else {}),
            }
            for b in profile.buttons
        ],
        "states": [
            {
                "name": s.name,
                "monitor_buttons": s.monitor_buttons,
                "transitions": s.transitions,
                "max_actions": s.max_actions,
            }
            for s in profile.states
        ],
        "ocr_regions": {k: list(v) for k, v in profile.ocr_regions.items()},
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def get_profiles_dir() -> Path:
    """Get the profiles directory (next to the package)."""
    return Path(__file__).parent.parent / "profiles"


def list_profiles() -> list:
    """List available profile names."""
    profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        return []
    return [f.stem for f in profiles_dir.glob("*.yaml")]


def get_default_profile() -> Profile:
    """Get the built-in Antimatter Dimensions default profile."""
    return Profile(
        name="antimatter_dimensions",
        game="Antimatter Dimensions",
        resolution=(3840, 2160),
        poll_interval=0.5,
        color_tolerance=3,
        buttons=[
            ButtonConfig("Antimatter Galaxies", 2076, 908, (103, 196, 90), cooldown=1.0),
            ButtonConfig("Dimension Boost", 860, 909, (103, 196, 90), cooldown=1.0),
            ButtonConfig("Big Crunch", 1512, 111, (51, 127, 182), cooldown=1.0),
            ButtonConfig("Max Ticks", 1546, 328, (103, 196, 90), cooldown=1.5),
        ],
        states=[
            StateConfig(
                name="farming",
                monitor_buttons=["Antimatter Galaxies", "Dimension Boost", "Big Crunch", "Max Ticks"],
                transitions={"Big Crunch": "crunching"},
                max_actions={"Antimatter Galaxies": 1, "Dimension Boost": 22},
            ),
            StateConfig(
                name="crunching",
                monitor_buttons=["Big Crunch"],
                transitions={"Big Crunch": "farming"},
            ),
        ],
        ocr_regions={
            "antimatter_count": (700, 50, 400, 40),
            "dimension_multiplier": (500, 200, 200, 30),
        },
    )
