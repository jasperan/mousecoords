from pathlib import Path

from mousecoords.backends.fixtures import FixtureScreenBackend
from mousecoords.vision import VisionEngine


FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_backend_can_find_template_match():
    backend = FixtureScreenBackend(FIXTURES / "screens" / "calculator_main.png")
    vision = VisionEngine(screen_backend=backend)

    center = vision.find_button_by_template(
        str(FIXTURES / "templates" / "digit_7.png"),
        confidence=0.9,
    )

    assert center == (26, 18)
