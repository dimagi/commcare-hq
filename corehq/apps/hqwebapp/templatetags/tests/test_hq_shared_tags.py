from datetime import datetime, timezone, timedelta

import pytest

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import iso_utc

EST = timezone(timedelta(hours=-5))


@pytest.mark.parametrize("dt, expected", [
    (
        datetime(2024, 3, 15, 12, 0, 0),
        "2024-03-15T12:00:00+00:00",
    ),
    (
        datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        "2024-03-15T12:00:00+00:00",
    ),
    (
        datetime(2024, 3, 15, 12, 0, 0, tzinfo=EST),
        "2024-03-15T17:00:00+00:00",
    ),
])
def test_iso_utc(dt, expected):
    assert iso_utc(dt) == expected
