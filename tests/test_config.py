"""Tests for the YAML profile configuration system."""

import pytest
from pathlib import Path

from mousecoords.config import (
    Profile, ButtonConfig, StateConfig,
    load_profile, save_profile, list_profiles,
    get_profiles_dir, get_default_profile,
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
