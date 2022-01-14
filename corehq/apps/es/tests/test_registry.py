from django.test import SimpleTestCase

from ..exceptions import ESRegistryError
from ..registry import (
    _ES_INFO_REGISTRY,
    _ALIAS_REF_COUNTS,
    register,
    deregister,
    verify_alias,
    verify_registered,
    registry_entry,
    get_registry,
)
from .utils import es_test


class INDEX_INFO:
    alias = "alias"


@es_test
class TestRegistry(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self._save_reg = _ES_INFO_REGISTRY.copy()
        self._save_als = _ALIAS_REF_COUNTS.copy()
        _ES_INFO_REGISTRY.clear()
        _ALIAS_REF_COUNTS.clear()

    def tearDown(self):
        _ES_INFO_REGISTRY.clear()
        _ALIAS_REF_COUNTS.clear()
        _ES_INFO_REGISTRY.update(self._save_reg)
        _ALIAS_REF_COUNTS.update(self._save_als)
        super().tearDown()

    def _register_one_and_check(self, info, cname):
        if cname is None:
            _cname = info.alias
        else:
            _cname = cname
        alias_ref_count = _ALIAS_REF_COUNTS.get(info.alias, 0)
        self.assertNotIn(_cname, _ES_INFO_REGISTRY)
        if cname is None:
            register(info)
        else:
            register(info, cname)
        entry = _ES_INFO_REGISTRY[_cname]
        self.assertIs(entry, info)
        self.assertEqual(_ALIAS_REF_COUNTS[info.alias], alias_ref_count + 1)

    def _deregister_one_and_check(self, info_or_cname, info):
        if info is None:
            alias = cname = info_or_cname.alias
        else:
            alias = info.alias
            if info_or_cname is None:
                info_or_cname = cname = alias
            else:
                cname = info_or_cname
        self.assertIn(cname, _ES_INFO_REGISTRY)
        alias_ref_count = _ALIAS_REF_COUNTS[alias]
        self.assertGreaterEqual(alias_ref_count, 1)
        deregister(info_or_cname)
        self.assertNotIn(cname, _ES_INFO_REGISTRY)
        self.assertEqual(_ALIAS_REF_COUNTS.get(alias, 0), alias_ref_count - 1)

    def _check_reg_lens(self, reg, als):
        self.assertEqual(len(_ES_INFO_REGISTRY), reg)
        self.assertEqual(len(_ALIAS_REF_COUNTS), als)

    def test_register_one_by_alias(self):
        self._check_reg_lens(0, 0)
        self._register_one_and_check(INDEX_INFO, None)
        self._check_reg_lens(1, 1)

    def test_register_one_by_cname(self):
        self._check_reg_lens(0, 0)
        self._register_one_and_check(INDEX_INFO, "canonical")
        self._check_reg_lens(1, 1)

    def test_register_multiple(self):
        self._check_reg_lens(0, 0)
        self._register_one_and_check(INDEX_INFO, None)
        self._check_reg_lens(1, 1)
        self._register_one_and_check(INDEX_INFO, "canonical")
        self._check_reg_lens(2, 1)

    def test_deregister_one_by_alias(self):
        register(INDEX_INFO)
        self._check_reg_lens(1, 1)
        self._deregister_one_and_check(INDEX_INFO, None)
        self.assertEqual(len(_ES_INFO_REGISTRY), 0)
        self.assertEqual(len(_ALIAS_REF_COUNTS), 0)

    def test_deregister_one_by_info(self):
        register(INDEX_INFO)
        self._check_reg_lens(1, 1)
        self._deregister_one_and_check(None, INDEX_INFO)
        self._check_reg_lens(0, 0)

    def test_deregister_one_by_cname(self):
        register(INDEX_INFO, "canonical")
        self._check_reg_lens(1, 1)
        self._deregister_one_and_check("canonical", INDEX_INFO)
        self._check_reg_lens(0, 0)

    def test_deregister_multiple(self):
        register(INDEX_INFO)
        register(INDEX_INFO, "canonical")
        self._check_reg_lens(2, 1)
        self._deregister_one_and_check("canonical", INDEX_INFO)
        self._check_reg_lens(1, 1)
        self._deregister_one_and_check(None, INDEX_INFO)
        self._check_reg_lens(0, 0)

    def test_verify_alias(self):
        with self.assertRaises(ESRegistryError):
            verify_alias(INDEX_INFO.alias)
        register(INDEX_INFO)
        verify_alias(INDEX_INFO.alias)  # should not raise ESRegistryError

    def test_verify_registered(self):
        with self.assertRaises(ESRegistryError):
            verify_registered(INDEX_INFO)
        register(INDEX_INFO)
        verify_registered(INDEX_INFO)  # should not raise ESRegistryError

    def test_registry_entry(self):
        with self.assertRaises(ESRegistryError):
            verify_registered(INDEX_INFO)
        register(INDEX_INFO)
        self.assertIs(registry_entry(INDEX_INFO.alias), INDEX_INFO)

    def test_get_registry(self):
        self.assertDictEqual(get_registry(), {})
        register(INDEX_INFO)
        self.assertDictEqual(get_registry(), {INDEX_INFO.alias: INDEX_INFO})
