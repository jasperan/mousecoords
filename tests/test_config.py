"""Tests for the YAML profile configuration system."""

import pytest
from pathlib import Path

from mousecoords.config import (
    Profile, ButtonConfig, StateConfig,
    load_profile, save_profile, list_profiles,
    get_profiles_dir, get_default_profile, get_demo_profile, DEFAULT_PROFILE_NAME, DEMO_PROFILE_NAME,
    resolve_profile_target, validate_profile,
)


class TestButtonConfig:
    def test_color_coerced_to_tuple(self):
        btn = ButtonConfig("test", 0, 0, [255, 128, 0])
        assert isinstance(btn.color, tuple)
        assert btn.color == (255, 128, 0)

    def test_defaults(self):
        btn = ButtonConfig("x", 10, 20, (0, 0, 0))
        assert btn.action == "click"
        assert btn.cooldown == 1.0
        assert btn.template is None
        assert btn.priority is False

    def test_priority_flag(self):
        btn = ButtonConfig("x", 0, 0, (0, 0, 0), priority=True)
        assert btn.priority is True


class TestProfile:
    def test_resolution_coerced_to_tuple(self):
        p = Profile(name="t", resolution=[1920, 1080])
        assert isinstance(p.resolution, tuple)

    def test_get_button(self, sample_profile):
        btn = sample_profile.get_button("Attack")
        assert btn is not None
        assert btn.x == 100

    def test_get_button_missing(self, sample_profile):
        assert sample_profile.get_button("NonExistent") is None

    def test_scale_to(self, sample_profile):
        scaled = sample_profile.scale_to(3840, 2160)
        assert scaled.resolution == (3840, 2160)
        # 100 * (3840/1920) = 200
        assert scaled.get_button("Attack").x == 200
        # 200 * (2160/1080) = 400
        assert scaled.get_button("Attack").y == 400

    def test_scale_preserves_priority(self, sample_profile):
        scaled = sample_profile.scale_to(3840, 2160)
        assert scaled.get_button("Attack").priority is True

    def test_scale_ocr_regions(self, sample_profile):
        scaled = sample_profile.scale_to(3840, 2160)
        # (10, 20, 100, 30) scaled 2x
        assert scaled.ocr_regions["health"] == (20, 40, 200, 60)


class TestProfileIO:
    def test_save_and_load(self, sample_profile, tmp_path):
        path = str(tmp_path / "test.yaml")
        save_profile(sample_profile, path)
        loaded = load_profile(path)

        assert loaded.name == sample_profile.name
        assert loaded.game == sample_profile.game
        assert loaded.resolution == sample_profile.resolution
        assert len(loaded.buttons) == len(sample_profile.buttons)
        assert loaded.buttons[0].name == "Attack"
        assert loaded.buttons[0].color == (255, 0, 0)
        assert len(loaded.states) == len(sample_profile.states)

    def test_save_creates_directory(self, sample_profile, tmp_path):
        path = str(tmp_path / "deep" / "nested" / "profile.yaml")
        save_profile(sample_profile, path)
        assert Path(path).exists()

    def test_load_ocr_regions_as_tuples(self, sample_profile, tmp_path):
        path = str(tmp_path / "test.yaml")
        save_profile(sample_profile, path)
        loaded = load_profile(path)
        for val in loaded.ocr_regions.values():
            assert isinstance(val, tuple)


class TestListProfiles:
    def test_list_profiles_finds_yaml(self):
        profiles = list_profiles()
        assert "antimatter_dimensions" in profiles

    def test_list_profiles_includes_pack_directories(self, sample_profile, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        pack_dir = profiles_dir / "pack_profile"
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: profiles_dir)
        save_profile(sample_profile, str(pack_dir / "profile.yaml"))
        profiles = list_profiles()
        assert "pack_profile" in profiles

    def test_list_profiles_includes_builtin_default_when_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: tmp_path / "missing")
        profiles = list_profiles()
        assert profiles == [DEFAULT_PROFILE_NAME, DEMO_PROFILE_NAME]

    def test_profiles_dir_exists(self):
        d = get_profiles_dir()
        assert d.exists()


class TestDefaultProfile:
    def test_default_has_buttons(self):
        p = get_default_profile()
        assert len(p.buttons) == 4

    def test_default_has_states(self):
        p = get_default_profile()
        assert len(p.states) == 2

    def test_default_galaxies_is_priority(self):
        p = get_default_profile()
        galaxies = p.get_button("Antimatter Galaxies")
        assert galaxies.priority is True

    def test_default_has_ocr_regions(self):
        p = get_default_profile()
        assert "antimatter_count" in p.ocr_regions


class TestDemoProfile:
    def test_demo_profile_has_buttons(self):
        profile = get_demo_profile()
        assert [button.name for button in profile.buttons] == ["Harvest", "Boost", "Reset"]

    def test_demo_profile_has_single_default_state(self):
        profile = get_demo_profile()
        assert [state.name for state in profile.states] == ["default"]


class TestResolveProfileTarget:
    def test_resolve_builtin_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: tmp_path / "missing")
        profile, path, source = resolve_profile_target()
        assert profile.name == DEFAULT_PROFILE_NAME
        assert path is None
        assert source == "builtin default profile"

    def test_resolve_named_profile(self, sample_profile, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: profiles_dir)
        save_profile(sample_profile, str(profiles_dir / "test_game.yaml"))
        profile, path, source = resolve_profile_target("test_game")
        assert profile.name == "test_game"
        assert path == profiles_dir / "test_game.yaml"
        assert source.endswith("test_game.yaml")

    def test_resolve_named_pack_profile(self, sample_profile, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: profiles_dir)
        pack_path = profiles_dir / "pack_game" / "profile.yaml"
        save_profile(sample_profile, str(pack_path))
        profile, path, source = resolve_profile_target("pack_game")
        assert profile.name == sample_profile.name
        assert path == pack_path
        assert source.endswith("pack_game/profile.yaml")

    def test_resolve_explicit_pack_directory(self, sample_profile, tmp_path):
        pack_dir = tmp_path / "explicit_pack"
        save_profile(sample_profile, str(pack_dir / "profile.yaml"))
        profile, path, source = resolve_profile_target(str(pack_dir))
        assert profile.name == sample_profile.name
        assert path == pack_dir / "profile.yaml"
        assert source.endswith("explicit_pack/profile.yaml")

    def test_resolve_builtin_demo_when_profiles_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mousecoords.config.get_profiles_dir", lambda: tmp_path / "missing")
        profile, path, source = resolve_profile_target(DEMO_PROFILE_NAME)
        assert profile.name == DEMO_PROFILE_NAME
        assert path is None
        assert source == "builtin demo profile"


class TestValidateProfile:
    def test_validate_valid_profile(self, sample_profile):
        result = validate_profile(sample_profile)
        assert result.ok is True
        assert result.issues == []

    def test_duplicate_button_names(self, sample_profile):
        sample_profile.buttons.append(ButtonConfig("Attack", 1, 1, (0, 0, 0)))
        result = validate_profile(sample_profile)
        assert result.ok is False
        assert any(issue.code == "duplicate_button" for issue in result.issues)

    def test_duplicate_state_names(self, sample_profile):
        sample_profile.states.append(StateConfig(name="combat"))
        result = validate_profile(sample_profile)
        assert any(issue.code == "duplicate_state" for issue in result.issues)

    def test_unknown_monitored_button(self, sample_profile):
        sample_profile.states[0].monitor_buttons.append("Missing Button")
        result = validate_profile(sample_profile)
        assert any(issue.code == "unknown_monitor_button" for issue in result.issues)

    def test_unknown_transition_target(self, sample_profile):
        sample_profile.states[0].transitions["Attack"] = "missing_state"
        result = validate_profile(sample_profile)
        assert any(issue.code == "unknown_transition_state" for issue in result.issues)

    def test_unknown_transition_trigger(self, sample_profile):
        sample_profile.states[0].transitions["Missing Button"] = "defend"
        result = validate_profile(sample_profile)
        assert any(issue.code == "unknown_transition_trigger" for issue in result.issues)

    def test_missing_template_file(self, sample_profile, tmp_path):
        sample_profile.buttons[0].template = "templates/missing.png"
        result = validate_profile(sample_profile, tmp_path / "profile.yaml")
        assert any(issue.code == "missing_template" for issue in result.issues)

    def test_invalid_ocr_region_shape(self, sample_profile):
        sample_profile.ocr_regions["health"] = (1, 2, 3)
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_ocr_region" for issue in result.issues)

    def test_invalid_ocr_region_dimensions(self, sample_profile):
        sample_profile.ocr_regions["health"] = (1, 2, 0, -1)
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_ocr_region" for issue in result.issues)

    def test_invalid_resolution(self, sample_profile):
        sample_profile.resolution = (1920, 0)
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_resolution" for issue in result.issues)

    def test_invalid_poll_interval(self, sample_profile):
        sample_profile.poll_interval = 0
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_poll_interval" for issue in result.issues)

    def test_invalid_color_tolerance(self, sample_profile):
        sample_profile.color_tolerance = -1
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_color_tolerance" for issue in result.issues)

    def test_invalid_button_coordinates(self, sample_profile):
        sample_profile.buttons[0].x = "10"
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_button_coordinates" for issue in result.issues)

    def test_invalid_button_color(self, sample_profile):
        sample_profile.buttons[0].color = (255, 255, 999)
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_button_color" for issue in result.issues)

    def test_invalid_button_cooldown(self, sample_profile):
        sample_profile.buttons[0].cooldown = -0.5
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_button_cooldown" for issue in result.issues)

    def test_unknown_max_action_button(self, sample_profile):
        sample_profile.states[0].max_actions["Missing Button"] = 1
        result = validate_profile(sample_profile)
        assert any(issue.code == "unknown_max_action_button" for issue in result.issues)

    def test_invalid_max_action_limit(self, sample_profile):
        sample_profile.states[0].max_actions["Attack"] = -1
        result = validate_profile(sample_profile)
        assert any(issue.code == "invalid_max_action_limit" for issue in result.issues)
