from pathlib import Path

import pytest

from app.security import safe_join, sanitize_filename, unique_destination


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("normal.txt", "normal.txt"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\evil.exe", "evil.exe"),
        ("a/b/c.txt", "c.txt"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("  spaced.txt  ", "spaced.txt"),
        ("bad\x00name.txt", "bad_name.txt"),
        ("", "file"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_long_names():
    long_name = ("a" * 300) + ".txt"
    result = sanitize_filename(long_name)
    assert len(result) <= 180
    assert result.endswith(".txt")


def test_safe_join_blocks_traversal(tmp_path):
    base = tmp_path / "jail"
    base.mkdir()
    with pytest.raises(ValueError):
        safe_join(base, "../outside.txt")
    with pytest.raises(ValueError):
        safe_join(base, "..", "..", "evil.txt")


def test_safe_join_allows_nested_path(tmp_path):
    base = tmp_path / "jail"
    base.mkdir()
    result = safe_join(base, "sub", "file.txt")
    assert result == (base / "sub" / "file.txt").resolve()


def test_unique_destination_avoids_overwrite(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"1")
    result = unique_destination(tmp_path, "photo.jpg")
    assert result.name == "photo (1).jpg"

    (tmp_path / "photo (1).jpg").write_bytes(b"2")
    result = unique_destination(tmp_path, "photo.jpg")
    assert result.name == "photo (2).jpg"
