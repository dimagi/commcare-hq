from io import StringIO
from textwrap import dedent

from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from ..utils import pprint


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

    def test_pprint(self):
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
                "examples": [
                    1637351249.036589,
                    1637351303,
                    "2021-11-19",
                    "__null__"
                ],
                "item": {
                    "null": "__null__"
                }
            }
        }""")
        result = StringIO()
        pprint(self.mapping, stream=result)
        self.assertEqual(result.getvalue(), expected)

    def test_pprint_with_namespace(self):
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
        pprint(self.mapping, namespace, stream=result)
        self.assertEqual(result.getvalue(), expected)
