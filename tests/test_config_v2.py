from mousecoords.config import list_profiles, load_profile


def test_loads_v2_profile_pack():
    profile = load_profile("profiles/calculator/profile.yaml")

    assert profile.schema_version == 2
    assert profile.targets[0].name == "digit_7"
    assert profile.app.window.title == "Calculator"


def test_list_profiles_includes_flat_and_pack_profiles():
    profiles = list_profiles()

    assert "antimatter_dimensions" in profiles
    assert "calculator" in profiles
