from django.test import SimpleTestCase

from corehq.apps.es.index.analysis import (
    DEFAULT_ANALYSIS,
    COMMA_ANALYSIS,
    LOWERCASE_WHITESPACE_ANALYZER,
    PHONETIC_ANALYSIS,
)
from corehq.apps.es.tests.utils import es_test


@es_test
class TestConstantValues(SimpleTestCase):
    """Test the constant values because they impact the how documents are
    analyzed when indexed, which affects how documents can be queried and which
    documents will be returned when queried.

    Changing these values will likely require reindexing the affected index(es).
    """

    def test_default_analyzer(self):
        self.assertEqual(
            {
                "type": "custom",
                "tokenizer": "whitespace",
                "filter": ["lowercase"]
            },
            LOWERCASE_WHITESPACE_ANALYZER,
        )

    def test_default_analysis(self):
        self.assertEqual(
            {"analyzer": {"default": LOWERCASE_WHITESPACE_ANALYZER}},
            DEFAULT_ANALYSIS,
        )

    def test_comma_analysis(self):
        self.assertEqual(
            {
                "analyzer": {
                    "default": LOWERCASE_WHITESPACE_ANALYZER,
                    "comma": {"type": "pattern", "pattern": r"\s*,\s*"},
                }
            },
            COMMA_ANALYSIS,
        )

    def test_phonetic_analysis(self):
        self.assertEqual(
            {
                "filter": {
                    "soundex": {
                        "replace": "true",
                        "type": "phonetic",
                        "encoder": "soundex"
                    }
                },
                "analyzer": {
                    "default": LOWERCASE_WHITESPACE_ANALYZER,
                    "phonetic": {
                        "filter": ["standard", "lowercase", "soundex"],
                        "tokenizer": "standard"
                    },
                }
            },
            PHONETIC_ANALYSIS,
        )
