from django.test import SimpleTestCase

import datetime
from corehq.ext.datetime import UTCDateTime

from corehq.ext.jsonobject import UTCDateTimeProperty
from corehq.ext.unittest import Corpus, CorpusMeta


class UTCDateTimePropertyTest(SimpleTestCase):
    __metaclass__ = CorpusMeta

    wrap = Corpus(UTCDateTimeProperty().wrap, {
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

    round_trip = Corpus(
        lambda string: UTCDateTimeProperty().unwrap(
            UTCDateTimeProperty().wrap(string))[1],
        {
            'no_tz': (
                '2014-10-08T21:51:04.568554',
                '2014-10-08T21:51:04.568554Z +00:00'
            ),
            'milliseconds': (
                '2014-10-08T21:51:04.568',
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
    )
