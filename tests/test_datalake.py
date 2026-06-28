import json

from src.datalake import (
    write_channel_messages_json,
    write_manifest,
)


def test_write_channel_messages_json(tmp_path):
    """Test writing channel messages to the data lake."""

    messages = [
        {
            "message_id": 1,
            "channel_name": "testchannel",
            "channel_title": "Test Channel",
            "message_date": "2026-06-28T10:00:00",
            "message_text": "Hello World",
            "has_media": False,
            "image_path": None,
            "views": 100,
            "forwards": 5,
        }
    ]

    write_channel_messages_json(
        base_path=str(tmp_path),
        date_str="2026-06-28",
        channel_name="testchannel",
        messages=messages,
    )

    output_file = (
        tmp_path
        / "raw"
        / "telegram_messages"
        / "2026-06-28"
        / "testchannel.json"
    )

    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["channel_name"] == "testchannel"
    assert data[0]["message_text"] == "Hello World"
    assert data[0]["views"] == 100


def test_write_manifest(tmp_path):
    """Test writing the daily manifest file."""

    counts = {
        "channel1": 10,
        "channel2": 5,
    }

    write_manifest(
        base_path=str(tmp_path),
        date_str="2026-06-28",
        channel_message_counts=counts,
    )

    manifest_file = (
        tmp_path
        / "raw"
        / "telegram_messages"
        / "2026-06-28"
        / "_manifest.json"
    )

    assert manifest_file.exists()

    with open(manifest_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["date"] == "2026-06-28"
    assert data["channels"] == counts
    assert data["total_messages"] == 15
    assert "run_utc" in data