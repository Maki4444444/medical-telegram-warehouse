import json
from pathlib import Path

from src.datalake import write_channel_messages_json, write_manifest


def test_write_channel_messages_json(tmp_path):
    messages = [
        {
            "message_id": 1,
            "channel_name": "testchannel",
            "channel_title": "Test Channel",
            "message_date": "2026-06-28T10:00:00",
            "message_text": "Hello",
            "has_media": False,
            "image_path": None,
            "views": 10,
            "forwards": 2,
        }
    ]

    write_channel_messages_json(
        base_path=str(tmp_path),
        date_str="2026-06-28",
        channel_name="testchannel",
        messages=messages,
    )

    output = (
        tmp_path
        / "raw"
        / "telegram_messages"
        / "2026-06-28"
        / "testchannel.json"
    )

    assert output.exists()

    with open(output, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["channel_name"] == "testchannel"


def test_write_manifest(tmp_path):
    counts = {
        "channel1": 10,
        "channel2": 5,
    }

    write_manifest(
        base_path=str(tmp_path),
        date_str="2026-06-28",
        channel_message_counts=counts,
    )

    manifest = (
        tmp_path
        / "raw"
        / "telegram_messages"
        / "2026-06-28"
        / "manifest.json"
    )

    assert manifest.exists()

    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)

    assert data["channel_message_counts"] == counts