"""Configuration system with YAML profiles for resolution-independent automation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def _tuple_or_value(value):
    return tuple(value) if isinstance(value, list) else value


@dataclass
class ButtonConfig:
    """Configuration for a single monitorable button."""

    name: str
    x: int
    y: int
    color: tuple
    action: str = "click"
    cooldown: float = 1.0
    template: Optional[str] = None

    def __post_init__(self):
        self.color = _tuple_or_value(self.color)


@dataclass
class SelectorConfig:
    """Configuration for a target selector in the v2 profile schema."""

    type: str
    path: Optional[str] = None
    confidence: Optional[float] = None
    point: Optional[tuple] = None
    rgb: Optional[tuple] = None
    tolerance: Optional[int] = None
    offset: Optional[tuple] = None
    rect: Optional[tuple] = None
    text: Optional[str] = None

    def __post_init__(self):
        self.point = _tuple_or_value(self.point)
        self.rgb = _tuple_or_value(self.rgb)
        self.offset = _tuple_or_value(self.offset)
        self.rect = _tuple_or_value(self.rect)


@dataclass
class ActionConfig:
    """Action to take once a target is resolved."""

    type: str = "click"
    cooldown: float = 1.0


@dataclass
class TargetConfig:
    """A named automation target with selector fallbacks."""

    name: str
    selectors: list = field(default_factory=list)
    action: ActionConfig = field(default_factory=ActionConfig)

    def __post_init__(self):
        self.selectors = [
            selector if isinstance(selector, SelectorConfig) else SelectorConfig(**selector)
            for selector in self.selectors
        ]
        if isinstance(self.action, dict):
            self.action = ActionConfig(**self.action)


@dataclass
class RegionConfig:
    """A named screen region, optionally with OCR settings."""

    name: str
    rect: tuple
    ocr: dict = field(default_factory=dict)

    def __post_init__(self):
        self.rect = _tuple_or_value(self.rect)
        self.ocr = dict(self.ocr or {})


@dataclass
class WindowConfig:
    """Window-matching metadata for desktop profile packs."""

    title: str = ""
    title_match: str = "exact"


@dataclass
class AppConfig:
    """App-level metadata for v2 profile packs."""

    window: WindowConfig = field(default_factory=WindowConfig)
    base_resolution: tuple = (1920, 1080)

    def __post_init__(self):
        if isinstance(self.window, dict):
            self.window = WindowConfig(**self.window)
        self.base_resolution = _tuple_or_value(self.base_resolution)


@dataclass
class RuntimeConfig:
    """Runtime configuration for v2 profile packs."""

    poll_interval: float = 0.5
    color_tolerance: int = 3
    scale_mode: str = "screen"
    dry_run_safe: bool = False


@dataclass
class StateConfig:
    """Configuration for a state machine state."""

    name: str
    monitor_buttons: list = field(default_factory=list)
    transitions: dict = field(default_factory=dict)
    max_actions: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "StateConfig":
        return cls(
            name=data["name"],
            monitor_buttons=list(data.get("monitor_buttons") or data.get("watch") or []),
            transitions=dict(data.get("transitions", {})),
            max_actions=dict(data.get("max_actions") or data.get("limits") or {}),
        )


@dataclass
class Profile:
    """Complete automation profile for a game or application."""

    name: str
    schema_version: int = 1
    kind: str = "game"
    game: str = ""
    resolution: tuple = (1920, 1080)
    poll_interval: float = 0.5
    color_tolerance: int = 3
    buttons: list = field(default_factory=list)
    targets: list = field(default_factory=list)
    regions: list = field(default_factory=list)
    states: list = field(default_factory=list)
    ocr_regions: dict = field(default_factory=dict)
    app: AppConfig = field(default_factory=AppConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    assets: dict = field(default_factory=dict)

    def __post_init__(self):
        self.resolution = _tuple_or_value(self.resolution)
        self.buttons = [
            button if isinstance(button, ButtonConfig) else ButtonConfig(**button)
            for button in self.buttons
        ]
        self.targets = [
            target if isinstance(target, TargetConfig) else TargetConfig(**target)
            for target in self.targets
        ]
        self.regions = [
            region if isinstance(region, RegionConfig) else RegionConfig(**region)
            for region in self.regions
        ]
        self.states = [
            state if isinstance(state, StateConfig) else StateConfig.from_dict(state)
            for state in self.states
        ]
        self.ocr_regions = {
            key: _tuple_or_value(value)
            for key, value in (self.ocr_regions or {}).items()
        }
        if isinstance(self.app, dict):
            self.app = AppConfig(**self.app)
        if isinstance(self.runtime, dict):
            self.runtime = RuntimeConfig(**self.runtime)
        self.assets = dict(self.assets or {})

        if self.schema_version >= 2:
            self.kind = self.kind or "desktop"
            self.resolution = self.app.base_resolution
            self.poll_interval = self.runtime.poll_interval
            self.color_tolerance = self.runtime.color_tolerance
            if not self.buttons and self.targets:
                self.buttons = _targets_to_legacy_buttons(self.targets)
            if not self.ocr_regions and self.regions:
                self.ocr_regions = {region.name: region.rect for region in self.regions}
        else:
            self.kind = self.kind or "game"
            self.app.base_resolution = self.resolution
            self.runtime.poll_interval = self.poll_interval
            self.runtime.color_tolerance = self.color_tolerance
            if not self.targets and self.buttons:
                self.targets = _buttons_to_targets(self.buttons)
            if not self.regions and self.ocr_regions:
                self.regions = _ocr_regions_to_regions(self.ocr_regions)

    def get_button(self, name: str) -> Optional[ButtonConfig]:
        """Look up a button by name."""
        for button in self.buttons:
            if button.name == name:
                return button
        return None

    def scale_to(self, target_w: int, target_h: int) -> "Profile":
        """Return a new profile with coordinates scaled to a different resolution."""
        src_w, src_h = self.resolution
        sx = target_w / src_w
        sy = target_h / src_h

        scaled_buttons = []
        for button in self.buttons:
            scaled_buttons.append(
                ButtonConfig(
                    name=button.name,
                    x=int(button.x * sx),
                    y=int(button.y * sy),
                    color=button.color,
                    action=button.action,
                    cooldown=button.cooldown,
                    template=button.template,
                )
            )

        scaled_ocr = {}
        for key, (rx, ry, rw, rh) in self.ocr_regions.items():
            scaled_ocr[key] = (
                int(rx * sx),
                int(ry * sy),
                int(rw * sx),
                int(rh * sy),
            )

        return Profile(
            name=self.name,
            schema_version=self.schema_version,
            kind=self.kind,
            game=self.game,
            resolution=(target_w, target_h),
            poll_interval=self.poll_interval,
            color_tolerance=self.color_tolerance,
            buttons=scaled_buttons,
            states=self.states,
            ocr_regions=scaled_ocr,
            app=AppConfig(window=self.app.window, base_resolution=(target_w, target_h)),
            runtime=RuntimeConfig(
                poll_interval=self.poll_interval,
                color_tolerance=self.color_tolerance,
                scale_mode=self.runtime.scale_mode,
                dry_run_safe=self.runtime.dry_run_safe,
            ),
            assets=self.assets,
        )


def _buttons_to_targets(buttons: list[ButtonConfig]) -> list[TargetConfig]:
    targets = []
    for button in buttons:
        if button.template:
            selector = SelectorConfig(type="template", path=button.template)
        else:
            selector = SelectorConfig(type="color", point=(button.x, button.y), rgb=button.color)
        targets.append(
            TargetConfig(
                name=button.name,
                selectors=[selector],
                action=ActionConfig(type=button.action, cooldown=button.cooldown),
            )
        )
    return targets


def _targets_to_legacy_buttons(targets: list[TargetConfig]) -> list[ButtonConfig]:
    buttons = []
    for target in targets:
        color_selector = next(
            (
                selector
                for selector in target.selectors
                if selector.type == "color" and selector.point and selector.rgb
            ),
            None,
        )
        template_selector = next(
            (
                selector
                for selector in target.selectors
                if selector.type in {"template", "anchor_template"} and selector.path
            ),
            None,
        )
        if not color_selector and not template_selector:
            continue

        x, y = color_selector.point if color_selector and color_selector.point else (0, 0)
        color = color_selector.rgb if color_selector and color_selector.rgb else (0, 0, 0)
        buttons.append(
            ButtonConfig(
                name=target.name,
                x=x,
                y=y,
                color=color,
                action=target.action.type,
                cooldown=target.action.cooldown,
                template=template_selector.path if template_selector else None,
            )
        )
    return buttons


def _ocr_regions_to_regions(ocr_regions: dict) -> list[RegionConfig]:
    return [
        RegionConfig(name=name, rect=_tuple_or_value(rect), ocr={"mode": "text"})
        for name, rect in ocr_regions.items()
    ]


def _load_v1_profile(data: dict) -> Profile:
    buttons = [ButtonConfig(**button) for button in data.get("buttons", [])]
    states = [StateConfig.from_dict(state) for state in data.get("states", [])]
    ocr_regions = {
        key: _tuple_or_value(value)
        for key, value in data.get("ocr_regions", {}).items()
    }

    return Profile(
        name=data["name"],
        schema_version=1,
        kind="game",
        game=data.get("game", ""),
        resolution=_tuple_or_value(data.get("resolution", [1920, 1080])),
        poll_interval=data.get("poll_interval", 0.5),
        color_tolerance=data.get("color_tolerance", 3),
        buttons=buttons,
        states=states,
        ocr_regions=ocr_regions,
    )


def _load_v2_profile(data: dict) -> Profile:
    targets = [TargetConfig(**target) for target in data.get("targets", [])]
    regions = [RegionConfig(**region) for region in data.get("regions", [])]
    states = [StateConfig.from_dict(state) for state in data.get("states", [])]

    return Profile(
        name=data["name"],
        schema_version=int(data.get("schema_version", 2)),
        kind=data.get("kind", "desktop"),
        targets=targets,
        regions=regions,
        states=states,
        app=AppConfig(**data.get("app", {})),
        runtime=RuntimeConfig(**data.get("runtime", {})),
        assets=data.get("assets", {}),
    )


def load_profile(path: str) -> Profile:
    """Load a profile from a YAML file."""
    with open(path) as handle:
        data = yaml.safe_load(handle) or {}

    schema_version = int(data.get("schema_version", 1) or 1)
    if schema_version >= 2:
        return _load_v2_profile(data)
    return _load_v1_profile(data)


def save_profile(profile: Profile, path: str):
    """Save a profile to a YAML file in the v2 schema."""
    target_path = Path(path)
    if target_path.suffix != ".yaml":
        target_path = target_path / "profile.yaml"

    targets = profile.targets or _buttons_to_targets(profile.buttons)
    regions = profile.regions or _ocr_regions_to_regions(profile.ocr_regions)
    app = profile.app or AppConfig(base_resolution=profile.resolution)
    runtime = profile.runtime or RuntimeConfig(
        poll_interval=profile.poll_interval,
        color_tolerance=profile.color_tolerance,
    )

    data = {
        "schema_version": 2,
        "kind": profile.kind or "desktop",
        "name": profile.name,
        "app": {
            "window": {
                "title": app.window.title,
                "title_match": app.window.title_match,
            },
            "base_resolution": list(app.base_resolution or profile.resolution),
        },
        "runtime": {
            "poll_interval": runtime.poll_interval,
            "color_tolerance": runtime.color_tolerance,
            "scale_mode": runtime.scale_mode,
            "dry_run_safe": runtime.dry_run_safe,
        },
        "targets": [
            {
                "name": target.name,
                "selectors": [
                    {
                        key: list(value) if isinstance(value, tuple) else value
                        for key, value in {
                            "type": selector.type,
                            "path": selector.path,
                            "confidence": selector.confidence,
                            "point": selector.point,
                            "rgb": selector.rgb,
                            "tolerance": selector.tolerance,
                            "offset": selector.offset,
                            "rect": selector.rect,
                            "text": selector.text,
                        }.items()
                        if value is not None
                    }
                    for selector in target.selectors
                ],
                "action": {
                    "type": target.action.type,
                    "cooldown": target.action.cooldown,
                },
            }
            for target in targets
        ],
        "regions": [
            {
                "name": region.name,
                "rect": list(region.rect),
                **({"ocr": region.ocr} if region.ocr else {}),
            }
            for region in regions
        ],
        "states": [
            {
                "name": state.name,
                "watch": state.monitor_buttons,
                "transitions": state.transitions,
                "limits": state.max_actions,
            }
            for state in profile.states
        ],
    }
    if profile.assets:
        data["assets"] = profile.assets

    os.makedirs(target_path.parent, exist_ok=True)
    with open(target_path, "w") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def get_profiles_dir() -> Path:
    """Get the profiles directory (next to the package)."""
    return Path(__file__).parent.parent / "profiles"


def list_profiles() -> list:
    """List available profile names from flat YAML files and profile packs."""
    profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        return []

    names = {path.stem for path in profiles_dir.glob("*.yaml")}
    names.update(path.parent.name for path in profiles_dir.glob("*/profile.yaml"))
    return sorted(names)


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
                monitor_buttons=[
                    "Antimatter Galaxies",
                    "Dimension Boost",
                    "Big Crunch",
                    "Max Ticks",
                ],
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
