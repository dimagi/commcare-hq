from io import StringIO
from textwrap import dedent

from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.utils import mapping_sort_key

from ..utils import print_formatted


@es_test
class TestMappingUtils(SimpleTestCase):

    maxDiff = 1024

    NULL = "__null__"
    EXAMPLES = [1637351249.036588954, 1637351303, "2021-11-19", NULL]

    mapping = {
        "alpha": {"true": True, "false": False, "zero": 0, "one": 1},
        "properties": {
            "@id": {"type": "integer"},
            "examples": EXAMPLES,
            "item": {"null": NULL},
        },
        "zulu": {"none": None},
    }

    def test_print_formatted(self):
        expected = dedent("""\
        {
            "alpha": {
                "false": False,
                "one": 1,
                "true": True,
                "zero": 0
            },
            "properties": {
                "@id": {
                    "type": "integer"
                },
                "examples": [
                    1637351249.036589,
                    1637351303,
                    "2021-11-19",
                    "__null__"
                ],
                "item": {
                    "null": "__null__"
                }
            },
            "zulu": {
                "none": None
            }
        }""")
        result = StringIO()
        print_formatted(self.mapping, stream=result)
        self.assertEqual(expected, result.getvalue())

    def test_print_formatted_with_namespace(self):
        expected = dedent("""\
        {
            "alpha": {
                "false": False,
                "one": 1,
                "true": True,
                "zero": 0
            },
            "properties": {
                "@id": {
                    "type": "integer"
                },
                "examples": EXAMPLES,
                "item": {
                    "null": NULL
                }
            },
            "zulu": {
                "none": None
            }
        }""")
        result = StringIO()
        namespace = {"EXAMPLES": self.EXAMPLES, "NULL": self.NULL}
        print_formatted(self.mapping, namespace, stream=result)
        self.assertEqual(expected, result.getvalue())

    def test_print_formatted_with_namespace_and_mapping_sort(self):
        expected = dedent("""\
        {
            "alpha": {
                "false": False,
                "one": 1,
                "true": True,
                "zero": 0
            },
            "zulu": {
                "none": None
            },
            "properties": {
                "@id": {
                    "type": "integer"
                },
                "examples": EXAMPLES,
                "item": {
                    "null": NULL
                }
            }
        }""")
        result = StringIO()
        namespace = {"EXAMPLES": self.EXAMPLES, "NULL": self.NULL}
        print_formatted(
            self.mapping,
            namespace,
            dict_sort_key=mapping_sort_key,
            stream=result,
        )
        self.assertEqual(expected, result.getvalue())
