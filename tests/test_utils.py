from pathlib import Path


def test_project_root_exists():
    """Project root should exist."""
    root = Path(__file__).resolve().parents[1]
    assert root.exists()


def test_logs_directory_name():
    """Simple sanity check."""
    assert "logs" == "logs"


def test_today_string_format():
    from datetime import datetime

    today = datetime.today().strftime("%Y-%m-%d")
    assert len(today) == 10
    assert today.count("-") == 2