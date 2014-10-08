import datetime
from django.test import SimpleTestCase
from iso8601.iso8601 import FixedOffset
from corehq.ext.datetime import UTCDateTime
from corehq.ext.unittest import CorpusMeta, Corpus, Raise, Call


class UTCDateTimeTest(SimpleTestCase):
    __metaclass__ = CorpusMeta

    tz_offset_to_string = Corpus(UTCDateTime.tz_offset_to_string, {
        'negative': (-datetime.timedelta(hours=4), '-04:00'),
        'minutes': (datetime.timedelta(hours=5, minutes=30), '+05:30'),
        'two_digit': (datetime.timedelta(hours=14), '+14:00'),
        'zero': (datetime.timedelta(hours=0), '+00:00'),
        'too_large': (datetime.timedelta(hours=16), Raise(ValueError)),
        'seconds_wrong': (datetime.timedelta(seconds=5), Raise(ValueError)),
        'minutes_45': (datetime.timedelta(hours=5, minutes=45), '+05:45'),
        'minutes_wrong': (datetime.timedelta(minutes=13), Raise(ValueError)),
    })

    tz_string_to_offset = Corpus(UTCDateTime.tz_string_to_offset, {
        'negative': ('-04:00', -datetime.timedelta(hours=4)),
        'minutes': ('+05:30', datetime.timedelta(hours=5, minutes=30)),
        'two_digit': ('+14:00', datetime.timedelta(hours=14)),
        'zero': ('+00:00', datetime.timedelta(hours=0)),
        'too_large': ('+16:00', Raise(ValueError)),
        'minutes_wrong': ('+00:05', Raise(ValueError)),
        'has_seconds': ('+10:00:12', Raise(ValueError)),
        'minutes_45': ('+05:45', datetime.timedelta(hours=5, minutes=45)),
        'missing_sign': ('05:30', Raise(ValueError)),
    })

    from_datetime = Corpus(UTCDateTime.from_datetime, {
        'fixed_offset': (
            datetime.datetime(2014, 12, 10, 22, 5, 18,
                              tzinfo=FixedOffset(3, 0, None)),
            UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00')
        ),
        'tz_naive': (
            datetime.datetime(2014, 10, 8, 16, 23, 9, tzinfo=None),
            UTCDateTime(2014, 10, 8, 16, 23, 9),
        ),
    })

    to_datetime = Corpus(UTCDateTime.to_datetime, {
        'basic': (
            UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
            datetime.datetime(2014, 12, 10, 22, 5, 18,
                              tzinfo=FixedOffset(3, 0, None))
        ),
    })

    test_equal = Corpus(UTCDateTime.__eq__, {
        'equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00')
            ),
            True
        ),
        'different_init_styles': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=3))
            ),
            True
        ),
        'ms_not_equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
                UTCDateTime(2014, 12, 10, 19, 5, 17, original_offset='+03:00')
            ),
            False
        ),
        'offset_not_equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+01:00')
            ),
            False
        ),
        'different_init_styles_not_equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=1))
            ),
            False
        ),
    })

    test_repr = Corpus(UTCDateTime.__repr__, {
        'same': (
            UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00'),
            "UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00')"
        ),
        'different_style': (
            UTCDateTime(2014, 12, 10, 19, 5, 18,
                        original_offset=datetime.timedelta(hours=3)),
            "UTCDateTime(2014, 12, 10, 19, 5, 18, original_offset='+03:00')"
        ),
    })
