from datetime import date, datetime

from django.test.testcases import SimpleTestCase
from pytz import UTC, timezone

from .utils import es_test
from ..utils import (
    ElasticJSONSerializer,
    SerializationError,
    es_format_datetime,
    sorted_mapping,
)

ET = timezone('US/Eastern')


@es_test
def test_es_format_datetime():
    def _assert_returns(date_or_datetime, expected):
        actual = es_format_datetime(date_or_datetime)
        assert actual == expected, f"Expected {expected}, got {actual}"

    for date_or_datetime, expected in [
            ("04/28/21", "04/28/21"),
            (date(2021, 4, 28), "2021-04-28"),
            (datetime(2021, 4, 28), "2021-04-28T00:00:00"),
            (datetime(2021, 4, 28, 11, 47, 22), "2021-04-28T11:47:22"),
            (datetime(2021, 4, 28, 11, 47, 22, 3), "2021-04-28T11:47:22.000003"),
            (datetime(2021, 4, 28, 11, 47, 22, 300000), "2021-04-28T11:47:22.300000"),
            (datetime(2021, 4, 28, 11, tzinfo=UTC), "2021-04-28T11:00:00+00:00"),
            (ET.localize(datetime(2021, 4, 28, 11)), "2021-04-28T11:00:00-04:00"),
            # 2021-04-28T11:00:00.000001-04:00 isn't supported in ES, so convert to server time
            (ET.localize(datetime(2021, 4, 28, 11, microsecond=1)), "2021-04-28T15:00:00.000001"),
    ]:
        yield _assert_returns, date_or_datetime, expected


@es_test
class TestElasticJSONSerializer(SimpleTestCase):

    def test_raises_elastic_exception(self):
        serializer = ElasticJSONSerializer()
        with self.assertRaises(SerializationError):
            serializer.loads("object")
        with self.assertRaises(SerializationError):
            serializer.dumps({"object": object()})


@es_test
class TestMappingsUtilsNoIndex(SimpleTestCase):

    def test_sorted_mapping(self):
        expected_order = ["alpha", "items", "zulu", "properties"]
        unsorted = {key: None for key in expected_order[::-1]}
        mapping = unsorted.copy()
        mapping["items"] = [unsorted.copy()]
        mapping["properties"] = unsorted.copy()
        mapping = sorted_mapping(mapping)
        self.assertEqual(expected_order, list(mapping))
        self.assertEqual(expected_order, list(mapping["items"][0]))
        self.assertEqual(expected_order, list(mapping["properties"]))
