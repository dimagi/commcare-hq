from django.test import SimpleTestCase

import datetime
from corehq.ext.datetime import UTCDateTime

from corehq.ext.jsonobject import UTCDateTimeProperty, ISOMeta
from corehq.ext.tests.utils import UTCDateTimeExactCorpus
from corehq.ext.unittest import Corpus, CorpusMeta
from jsonobject import JsonObject


class UTCDateTimePropertyTest(SimpleTestCase):
    __metaclass__ = CorpusMeta

    wrap = UTCDateTimeExactCorpus(UTCDateTimeProperty().wrap, {
        'positive_tz': (
            '2014-12-11T01:05:18+03:00',
            UTCDateTime(2014, 12, 10, 22, 5, 18,
                        original_offset=datetime.timedelta(hours=3))
        ),
        'date_only': ('2014-12-11', UTCDateTime(2014, 12, 11)),
        'utc_datetime_with_offset': (
            '2014-12-10T22:05:18.000000Z +03:00',
            UTCDateTime(2014, 12, 10, 22, 5, 18,
                        original_offset=datetime.timedelta(hours=3))
        ),
    })

    unwrap = UTCDateTimeExactCorpus(UTCDateTimeProperty().unwrap, {
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
            (UTCDateTime(2014, 12, 11, 0, 0), '2014-12-11T00:00:00.000000')
        ),
    })

    ROUND_TRIP_CASES = {
        'no_tz': (
            '2014-10-08T21:51:04.568554',
            '2014-10-08T21:51:04.568554'
        ),
        'no_tz_milliseconds': (
            '2014-10-08T21:51:04.568',
            '2014-10-08T21:51:04.568000'
        ),
        'milliseconds': (
            '2014-10-08T21:51:04.568Z',
            '2014-10-08T21:51:04.568000Z +00:00'
        ),
        'Z': (
            '2014-10-08T21:51:04.568554Z',
            '2014-10-08T21:51:04.568554Z +00:00'
        ),
        'tz': (
            '2014-10-08T17:51:04.568554-04:00',
            '2014-10-08T21:51:04.568554Z -04:00'
        ),
        'same': (
            '2014-10-08T21:51:04.568554Z -04:00',
            '2014-10-08T21:51:04.568554Z -04:00'
        )

    }

    round_trip = Corpus(
        lambda string: UTCDateTimeProperty().unwrap(
            UTCDateTimeProperty().wrap(string))[1],
        ROUND_TRIP_CASES,
    )

    double_round_trip = Corpus(
        lambda string: UTCDateTimeProperty().unwrap(UTCDateTimeProperty().wrap(
            UTCDateTimeProperty().unwrap(UTCDateTimeProperty().wrap(string))[1]
        ))[1],
        ROUND_TRIP_CASES,
    )


class TestISOMeta(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        class Foo(JsonObject):
            Meta = ISOMeta

        cls.Foo = Foo

    def test_dynamic(self):
        foo = self.Foo.wrap({
            'datetime': '2014-01-01T00:00:00.123Z',
        })
        self.assertEqual(foo.datetime, UTCDateTime(2014, 1, 1, 0, 0, 0, 123000,
                                                   original_offset='+00:00'))
