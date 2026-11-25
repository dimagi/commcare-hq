import pytest

from corehq.util.download import RangeNotSatisfiableError, parse_byte_range


@pytest.mark.parametrize("header, expected", [
    ("bytes=0-499", (0, 500)),
    ("bytes=500-999", (500, 1000)),
    ("bytes=0-0", (0, 1)),
    ("bytes=999-999", (999, 1000)),
    ("bytes=500-", (500, 1000)),
    ("bytes=0-", (0, 1000)),
    ("bytes=-200", (800, 1000)),
    ("bytes=500-5000", (500, 1000)),  # last-pos beyond content is clamped
    ("bytes=-5000", (0, 1000)),  # suffix longer than content
    ("BYTES=0-499", (0, 500)),
    (" bytes=0-499 ", (0, 500)),
])
def test_parse_byte_range(header, expected):
    assert parse_byte_range(header, 1000) == expected


@pytest.mark.parametrize("header", [
    "",
    "bytes=",
    "bytes=-",
    "bytes=abc-def",
    "bytes=500-499",
    "bytes=0-1,5-6",
    "bytes=-1-2",
    "bytes 0-499",
    "items=0-499",
    "bytes=١-٢",  # non-ASCII digits
])
def test_parse_byte_range_ignored(header):
    assert parse_byte_range(header, 1000) is None


@pytest.mark.parametrize("header, content_length", [
    ("bytes=1000-", 1000),
    ("bytes=1000-1999", 1000),
    ("bytes=-0", 1000),
    ("bytes=0-", 0),
    ("bytes=-10", 0),
])
def test_parse_byte_range_not_satisfiable(header, content_length):
    with pytest.raises(RangeNotSatisfiableError):
        parse_byte_range(header, content_length)
