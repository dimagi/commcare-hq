from django.test import SimpleTestCase
from mock import patch

from ..exceptions import ESRegistryError
from ..registry import (
    ES_META,
    register_alias,
    deregister_alias,
    verify_registered_alias,
)
from .utils import es_test


class INDEX_INFO:
    alias = "alias"


@es_test
class TestRegistry(SimpleTestCase):

    @patch.dict(ES_META, {})
    def test_register_alias(self):
        self.assertNotIn(INDEX_INFO.alias, ES_META)
        register_alias(INDEX_INFO.alias, INDEX_INFO)
        self.assertIn(INDEX_INFO.alias, ES_META)
        self.assertIs(ES_META[INDEX_INFO.alias], INDEX_INFO)

    @patch.dict(ES_META, {})
    def test_deregister_alias(self):
        register_alias(INDEX_INFO.alias, INDEX_INFO)
        self.assertIn(INDEX_INFO.alias, ES_META)
        deregister_alias(INDEX_INFO.alias)
        self.assertNotIn(INDEX_INFO.alias, ES_META)

    @patch.dict(ES_META, {})
    def test_verify_registered_alias(self):
        with self.assertRaises(ESRegistryError):
            verify_registered_alias(INDEX_INFO.alias)
        register_alias(INDEX_INFO.alias, INDEX_INFO)
        verify_registered_alias(INDEX_INFO.alias)  # should not raise ESRegistryError
