from pathlib import Path

from mousecoords.backends.fixtures import FixtureScreenBackend
from mousecoords.vision import VisionEngine


FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_backend_can_read_pixel():
    backend = FixtureScreenBackend(FIXTURES / "screens" / "calculator_main.png")
    vision = VisionEngine(screen_backend=backend)

    assert vision.get_pixel_color(10, 10) == (255, 255, 255)
