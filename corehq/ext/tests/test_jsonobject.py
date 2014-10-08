import datetime
from django.test import SimpleTestCase
from iso8601.iso8601 import FixedOffset
from corehq.ext.jsonobject import UTCDateTimeProperty, UTCDateTime
from corehq.ext.unittest import Corpus, Raise, CorpusMeta, Call


class UTCDateTimeTest(SimpleTestCase):
    __metaclass__ = CorpusMeta

    format_tz_string = Corpus(UTCDateTime.format_tz_string, {
        'negative': (-datetime.timedelta(hours=4), '-04:00'),
        'minutes': (datetime.timedelta(hours=5, minutes=30), '+05:30'),
        'two_digit': (datetime.timedelta(hours=14), '+14:00'),
        'zero': (datetime.timedelta(hours=0), '+00:00'),
        'too_large': (datetime.timedelta(hours=16), Raise(AssertionError)),
        'seconds_wrong': (datetime.timedelta(seconds=5), Raise(AssertionError)),
        'minutes_wrong': (datetime.timedelta(minutes=15), Raise(AssertionError)),
    })

    from_datetime = Corpus(UTCDateTime.from_datetime, {
        'fixed_offset': (
            datetime.datetime(2014, 12, 10, 22, 5, 18,
                              tzinfo=FixedOffset(3, 0, None)),
            UTCDateTime(2014, 12, 10, 19, 5, 18,
                        original_offset=datetime.timedelta(hours=3))
        ),
        'tz_naive': (
            datetime.datetime(2014, 10, 8, 16, 23, 9, tzinfo=None),
            UTCDateTime(2014, 10, 8, 16, 23, 9),
        ),
    })

    test_equal = Corpus(UTCDateTime.__eq__, {
        'equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=3)),
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=3))
            ),
            True
        ),
        'ms_not_equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=3)),
                UTCDateTime(2014, 12, 10, 19, 5, 17,
                            original_offset=datetime.timedelta(hours=3))
            ),
            False
        ),
        'offset_not_equal': (
            Call(
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=3)),
                UTCDateTime(2014, 12, 10, 19, 5, 18,
                            original_offset=datetime.timedelta(hours=1))
            ),
            False
        )
    })


class UTCDateTimeProperty(SimpleTestCase):
    __metaclass__ = CorpusMeta

    wrap = Corpus(UTCDateTimeProperty().wrap, {
        'positive_tz': (
            '2014-12-11T01:05:18+03:00',
            UTCDateTime(2014, 12, 10, 22, 5, 18,
                        original_offset=datetime.timedelta(hours=3))
        ),
        'date_only': ('2014-12-11', UTCDateTime(2014, 12, 11)),
    })

    unwrap = Corpus(UTCDateTimeProperty().unwrap, {
        'positive_tz': (
            UTCDateTime(2014, 12, 10, 22, 5, 18,
                        original_offset=datetime.timedelta(hours=3)),
            (
                UTCDateTime(2014, 12, 10, 22, 5, 18,
                            original_offset=datetime.timedelta(hours=3)),
                '2014-12-10T22:05:18.000000Z +03:00'
            )
        ),
        'date_only': (
            UTCDateTime(2014, 12, 11, 0, 0),
            (UTCDateTime(2014, 12, 11, 0, 0),
             '2014-12-11T00:00:00.000000Z +00:00')
        ),
    })
