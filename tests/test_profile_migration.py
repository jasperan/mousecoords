from mousecoords.config import load_profile


def test_loads_v1_profile_and_migrates_to_targets():
    profile = load_profile("profiles/antimatter_dimensions.yaml")

    assert profile.targets
    assert profile.targets[0].selectors
    assert profile.regions
