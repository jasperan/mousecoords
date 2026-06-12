"""Configuration system with YAML profiles for resolution-independent automation."""

from __future__ import annotations

import os
import yaml
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Optional
from pathlib import Path

DEFAULT_PROFILE_NAME = "antimatter_dimensions"
DEMO_PROFILE_NAME = "desktop_demo"


def _pack_profile_path(directory: Path) -> Path:
    """Return the canonical profile file inside a profile-pack directory."""
    return directory / "profile.yaml"


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
    priority: bool = False  # if True, skip remaining buttons after clicking this one

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

        scaled_buttons = [
            replace(b, x=int(b.x * sx), y=int(b.y * sy))
            for b in self.buttons
        ]

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


@dataclass
class ValidationIssue:
    """Single actionable validation finding for a profile."""
    level: str
    code: str
    message: str


@dataclass
class ProfileValidationResult:
    """Aggregate validation result for a profile."""
    profile_name: str
    source: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def add(self, code: str, message: str, level: str = "error"):
        self.issues.append(ValidationIssue(level=level, code=code, message=message))

    def to_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "source": self.source,
            "ok": self.ok,
            "issues": [
                {
                    "level": issue.level,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


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


def resolve_profile_target(target: Optional[str] = None) -> tuple[Profile, Optional[Path], str]:
    """Resolve a profile by path or name, with a built-in default fallback."""
    if target:
        explicit_path = Path(target)
        if explicit_path.exists():
            if explicit_path.is_dir():
                pack_path = _pack_profile_path(explicit_path)
                if not pack_path.exists():
                    raise FileNotFoundError(
                        f"Profile directory '{explicit_path}' does not contain {pack_path.name}."
                    )
                return load_profile(str(pack_path)), pack_path, str(pack_path)
            return load_profile(str(explicit_path)), explicit_path, str(explicit_path)

        named_path = None
        if explicit_path.suffix != ".yaml":
            named_path = get_profiles_dir() / f"{target}.yaml"
            if named_path.exists():
                return load_profile(str(named_path)), named_path, str(named_path)

        pack_path = _pack_profile_path(get_profiles_dir() / target)
        if pack_path.exists():
            return load_profile(str(pack_path)), pack_path, str(pack_path)

        if is_default_profile_name(target):
            return get_default_profile(), None, "builtin default profile"
        if is_demo_profile_name(target):
            return get_demo_profile(), None, "builtin demo profile"

        expected = named_path if named_path is not None else explicit_path
        raise FileNotFoundError(
            f"Profile '{target}' not found. Expected a YAML path or {expected}."
        )

    default_path = get_profiles_dir() / f"{DEFAULT_PROFILE_NAME}.yaml"
    if default_path.exists():
        return load_profile(str(default_path)), default_path, str(default_path)
    return get_default_profile(), None, "builtin default profile"


def save_profile(profile: Profile, path: str):
    """Save a profile to a YAML file."""
    data = profile_to_data(profile)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def profile_to_data(profile: Profile) -> dict:
    """Serialize a profile into the YAML-friendly shape used on disk."""
    return {
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
                **({"priority": b.priority} if b.priority else {}),
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


def get_profiles_dir() -> Path:
    """Get the profiles directory (next to the package)."""
    return Path(__file__).parent.parent / "profiles"


def get_demo_profile() -> Profile:
    """Get the built-in deterministic desktop demo profile."""
    return Profile(
        name=DEMO_PROFILE_NAME,
        game="mousecoords Demo Lab",
        resolution=(1280, 1024),
        poll_interval=0.05,
        color_tolerance=8,
        buttons=[
            ButtonConfig("Harvest", 210, 240, (220, 70, 70), cooldown=0.2),
            ButtonConfig("Boost", 330, 240, (70, 170, 70), cooldown=0.2),
            ButtonConfig("Reset", 450, 240, (70, 120, 220), cooldown=0.2),
        ],
        states=[
            StateConfig(
                name="default",
                monitor_buttons=["Harvest", "Boost", "Reset"],
                transitions={},
                max_actions={},
            )
        ],
        ocr_regions={},
    )


def is_default_profile_name(name: str) -> bool:
    """Return True when a requested profile name is the built-in default."""
    return name == DEFAULT_PROFILE_NAME


def is_demo_profile_name(name: str) -> bool:
    """Return True when a requested profile name is the built-in demo."""
    return name == DEMO_PROFILE_NAME


def list_profiles() -> list:
    """List available profile names."""
    profiles_dir = get_profiles_dir()
    names = []
    if profiles_dir.exists():
        names.extend(f.stem for f in profiles_dir.glob("*.yaml"))
        names.extend(
            path.parent.name
            for path in profiles_dir.glob("*/profile.yaml")
        )
    if DEFAULT_PROFILE_NAME not in names:
        names.append(DEFAULT_PROFILE_NAME)
    if DEMO_PROFILE_NAME not in names:
        names.append(DEMO_PROFILE_NAME)
    return sorted(set(names))


def resolve_template_path(template: str, profile_path: Optional[Path] = None) -> Optional[Path]:
    """Resolve a template reference using common profile/project-relative locations."""
    template_path = Path(template)
    candidates = []

    if template_path.is_absolute():
        candidates.append(template_path)
    else:
        if profile_path is not None:
            candidates.append(profile_path.parent / template_path)
        project_root = get_profiles_dir().parent
        candidates.append(project_root / template_path)
        candidates.append(Path.cwd() / template_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def validate_profile(profile: Profile, profile_path: Optional[str | Path] = None) -> ProfileValidationResult:
    """Validate profile structure and referenced assets."""
    source = str(profile_path) if profile_path else "builtin default profile"
    resolved_profile_path = Path(profile_path) if profile_path else None
    result = ProfileValidationResult(profile_name=profile.name, source=source)

    if (
        not isinstance(profile.resolution, tuple)
        or len(profile.resolution) != 2
        or not all(isinstance(value, int) for value in profile.resolution)
        or any(value <= 0 for value in profile.resolution)
    ):
        result.add(
            "invalid_resolution",
            "Resolution must be a 2-item positive integer tuple/list [width, height].",
        )

    if not isinstance(profile.poll_interval, (int, float)) or profile.poll_interval <= 0:
        result.add("invalid_poll_interval", "poll_interval must be a positive number.")

    if not isinstance(profile.color_tolerance, int) or profile.color_tolerance < 0:
        result.add("invalid_color_tolerance", "color_tolerance must be a non-negative integer.")

    button_names = [button.name for button in profile.buttons]
    state_names = [state.name for state in profile.states]

    for name, count in Counter(button_names).items():
        if count > 1:
            result.add("duplicate_button", f"Button '{name}' is defined {count} times.")

    for name, count in Counter(state_names).items():
        if count > 1:
            result.add("duplicate_state", f"State '{name}' is defined {count} times.")

    button_name_set = set(button_names)
    state_name_set = set(state_names)

    for button in profile.buttons:
        if not isinstance(button.x, int) or not isinstance(button.y, int):
            result.add(
                "invalid_button_coordinates",
                f"Button '{button.name}' must use integer x/y coordinates.",
            )

        if (
            not isinstance(button.color, tuple)
            or len(button.color) != 3
            or not all(isinstance(value, int) for value in button.color)
            or any(value < 0 or value > 255 for value in button.color)
        ):
            result.add(
                "invalid_button_color",
                f"Button '{button.name}' must use an RGB tuple/list of three integers between 0 and 255.",
            )

        if not isinstance(button.cooldown, (int, float)) or button.cooldown < 0:
            result.add(
                "invalid_button_cooldown",
                f"Button '{button.name}' must use a non-negative cooldown.",
            )

        if button.template and resolve_template_path(button.template, resolved_profile_path) is None:
            result.add(
                "missing_template",
                f"Button '{button.name}' references missing template '{button.template}'.",
            )

    for state in profile.states:
        for button_name in state.monitor_buttons:
            if button_name not in button_name_set:
                result.add(
                    "unknown_monitor_button",
                    f"State '{state.name}' references unknown button '{button_name}'.",
                )

        for trigger, destination in state.transitions.items():
            if trigger not in button_name_set:
                result.add(
                    "unknown_transition_trigger",
                    f"State '{state.name}' transitions on unknown button '{trigger}'.",
                )
            if destination not in state_name_set:
                result.add(
                    "unknown_transition_state",
                    f"State '{state.name}' transitions to missing state '{destination}'.",
                )

        for button_name, limit in state.max_actions.items():
            if button_name not in button_name_set:
                result.add(
                    "unknown_max_action_button",
                    f"State '{state.name}' sets max_actions for unknown button '{button_name}'.",
                )
            if not isinstance(limit, int) or limit < 0:
                result.add(
                    "invalid_max_action_limit",
                    f"State '{state.name}' must use non-negative integer limits for '{button_name}'.",
                )

    for region_name, region in profile.ocr_regions.items():
        if not isinstance(region, tuple) or len(region) != 4:
            result.add(
                "invalid_ocr_region",
                f"OCR region '{region_name}' must be a 4-item tuple/list [x, y, width, height].",
            )
            continue
        if not all(isinstance(value, int) for value in region):
            result.add(
                "invalid_ocr_region",
                f"OCR region '{region_name}' must contain integer coordinates.",
            )
            continue
        _, _, width, height = region
        if width <= 0 or height <= 0:
            result.add(
                "invalid_ocr_region",
                f"OCR region '{region_name}' must have positive width and height.",
            )

    return result


def get_default_profile() -> Profile:
    """Get the built-in Antimatter Dimensions default profile."""
    return Profile(
        name=DEFAULT_PROFILE_NAME,
        game="Antimatter Dimensions",
        resolution=(3840, 2160),
        poll_interval=0.5,
        color_tolerance=3,
        buttons=[
            ButtonConfig("Antimatter Galaxies", 2076, 908, (103, 196, 90),
                         cooldown=1.0, priority=True),
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
