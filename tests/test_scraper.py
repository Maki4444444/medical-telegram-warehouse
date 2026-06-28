import tempfile
from pathlib import Path

from src.scraper import _create_placeholder_image


def test_placeholder_image_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "sample.jpg"

        _create_placeholder_image(
            str(image_path),
            channel_name="CheMed123",
            msg_id=100,
            text_snippet="Testing image generation."
        )

        assert image_path.exists()
        assert image_path.stat().st_size > 0


def test_channel_color_exists():
    from src.scraper import CHANNEL_COLORS

    assert "CheMed123" in CHANNEL_COLORS
    assert "lobelia4cosmetics" in CHANNEL_COLORS
    assert "tikvahpharma" in CHANNEL_COLORS


def test_sample_messages_exist():
    from src.scraper import SAMPLE_MESSAGES

    assert len(SAMPLE_MESSAGES) == 3

    for channel in SAMPLE_MESSAGES.values():
        assert "title" in channel
        assert "posts" in channel
        assert len(channel["posts"]) > 0