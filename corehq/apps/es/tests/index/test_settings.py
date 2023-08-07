from unittest.mock import patch

from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.apps.es.index.settings import (
    DEFAULT,
    DEFAULT_REPLICAS,
    DEFAULT_SHARDS,
    DEFAULT_TUNING_SETTINGS,
    REMOVE_SETTING,
    IndexSettingsKey,
    IndexTuningKey,
    InvalidTuningSettingsError,
    SettingsKeyCollection,
    render_index_tuning_settings,
)
from corehq.apps.es.tests.utils import es_test, ignore_index_settings_key_warning


def overridden_index_settings():
    """Returns a dict of index settings.

    Tests use this to plug settings when they need values to be present which
    they wish to verify will not to be part of the final rendered result.
    """
    return {
        IndexTuningKey.REPLICAS: object(),
        IndexTuningKey.SHARDS: object(),
    }


@es_test
@ignore_index_settings_key_warning
@override_settings(ES_SETTINGS=None)
class TestRenderSettings(SimpleTestCase):

    TEST_REPLICAS = object()
    TEST_SHARDS = object()

    def test_render_index_tuning_settings_returns_module_defaults(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), DEFAULT_REPLICAS)
        self.assertEqual(settings.pop(IndexTuningKey.SHARDS), DEFAULT_SHARDS)
        self.assertEqual({}, settings)

    @patch("corehq.apps.es.index.settings.DEFAULT_TUNING_SETTINGS", {
        DEFAULT: overridden_index_settings(),
        "test": {
            IndexTuningKey.REPLICAS: TEST_REPLICAS,
            IndexTuningKey.SHARDS: TEST_SHARDS,
        }
    })
    def test_render_index_tuning_settings_module_settings_by_name_override_module_defaults(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), self.TEST_REPLICAS)
        self.assertEqual(settings.pop(IndexTuningKey.SHARDS), self.TEST_SHARDS)
        self.assertEqual({}, settings)

    @patch("corehq.apps.es.index.settings.DEFAULT_TUNING_SETTINGS", {
        DEFAULT: overridden_index_settings(),
        "test": overridden_index_settings(),
    })
    @override_settings(ES_SETTINGS={
        DEFAULT: {
            IndexTuningKey.REPLICAS: TEST_REPLICAS,
            IndexTuningKey.SHARDS: TEST_SHARDS,
        }
    })
    def test_render_index_tuning_settings_default_django_settings_override_module_values(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), self.TEST_REPLICAS)
        self.assertEqual(settings.pop(IndexTuningKey.SHARDS), self.TEST_SHARDS)
        self.assertEqual({}, settings)

    @patch("corehq.apps.es.index.settings.DEFAULT_TUNING_SETTINGS", {
        DEFAULT: overridden_index_settings(),
        "test": overridden_index_settings(),
    })
    @override_settings(ES_SETTINGS={
        DEFAULT: overridden_index_settings(),
        "test": {
            IndexTuningKey.REPLICAS: TEST_REPLICAS,
            IndexTuningKey.SHARDS: TEST_SHARDS,
        }
    })
    def test_render_index_tuning_settings_django_settings_by_name_override_all(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), self.TEST_REPLICAS)
        self.assertEqual(settings.pop(IndexTuningKey.SHARDS), self.TEST_SHARDS)
        self.assertEqual({}, settings)

    @override_settings(ES_SETTINGS={
        "test": {
            IndexTuningKey.REPLICAS: TEST_REPLICAS,
            IndexTuningKey.SHARDS: REMOVE_SETTING,
        }
    })
    def test_render_index_tuning_settings_special_remove_value_omits_setting(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), self.TEST_REPLICAS)
        self.assertEqual({}, settings)

    @override_settings(ES_SETTINGS={
        DEFAULT: {
            IndexTuningKey.SHARDS: REMOVE_SETTING,
        },
        "test": {
            IndexTuningKey.REPLICAS: TEST_REPLICAS,
            IndexTuningKey.SHARDS: TEST_SHARDS,
        }
    })
    def test_render_index_tuning_settings_special_remove_value_is_overridden_by_later_values(self):
        settings = render_index_tuning_settings("test")
        self.assertEqual(settings.pop(IndexTuningKey.REPLICAS), self.TEST_REPLICAS)
        self.assertEqual(settings.pop(IndexTuningKey.SHARDS), self.TEST_SHARDS)
        self.assertEqual({}, settings)

    @override_settings(ES_SETTINGS={
        DEFAULT: {
            "not_a_valid_setting": True,
        }
    })
    def test_render_index_tuning_settings_invalid_settings_key_raises_invalidtuningsettingserror(self):
        with self.assertRaises(InvalidTuningSettingsError):
            render_index_tuning_settings("test")


@es_test
class TestConstantValues(SimpleTestCase):
    """Test the constant values because they impact the format and values of
    localsettings variables, commcare-cloud configurations, and also downstream
    Elasticsearch cluster configurations.

    Changing these values have an impact outside of the commcare-hq codebase and
    may require announcements on the forum.
    """

    def test_remove_value(self):
        self.assertIsNone(REMOVE_SETTING)

    def test_default(self):
        self.assertEqual("default", DEFAULT)

    def test_index_settings_key_attrs(self):
        self.assertEqual("hqapps", IndexSettingsKey.APPS)
        self.assertEqual("hqcases", IndexSettingsKey.CASES)
        self.assertEqual("case_search", IndexSettingsKey.CASE_SEARCH)
        self.assertEqual("hqdomains", IndexSettingsKey.DOMAINS)
        self.assertEqual("xforms", IndexSettingsKey.FORMS)
        self.assertEqual("hqgroups", IndexSettingsKey.GROUPS)
        self.assertEqual("smslogs", IndexSettingsKey.SMS)
        self.assertEqual("hqusers", IndexSettingsKey.USERS)

    def test_index_settings_keys_members(self):
        self.assertEqual(
            [
                "case_search", "hqapps", "hqcases", "hqdomains", "hqgroups",
                "hqusers", "smslogs", "xforms",
            ],
            sorted(IndexSettingsKey),
        )

    def test_index_tuning_key_attrs(self):
        self.assertEqual("number_of_replicas", IndexTuningKey.REPLICAS)
        self.assertEqual("number_of_shards", IndexTuningKey.SHARDS)

    def test_index_tuning_key_members(self):
        self.assertEqual(
            ["number_of_replicas", "number_of_shards"],
            sorted(IndexTuningKey),
        )

    def test_default_replicas(self):
        self.assertEqual(0, DEFAULT_REPLICAS)

    def test_default_shards(self):
        self.assertEqual(5, DEFAULT_SHARDS)

    def test_default_tuning_settings(self):
        self.assertEqual(
            {
                DEFAULT: {
                    IndexTuningKey.REPLICAS: DEFAULT_REPLICAS,
                    IndexTuningKey.SHARDS: DEFAULT_SHARDS,
                },
                IndexSettingsKey.APPS: {
                    IndexTuningKey.REPLICAS: 0,
                },
                IndexSettingsKey.CASE_SEARCH: {
                    IndexTuningKey.REPLICAS: 1,
                    IndexTuningKey.SHARDS: 5,
                },
                IndexSettingsKey.DOMAINS: {
                    IndexTuningKey.REPLICAS: 0,
                },
                IndexSettingsKey.USERS: {
                    IndexTuningKey.REPLICAS: 0,
                    IndexTuningKey.SHARDS: 2,
                },
            },
            DEFAULT_TUNING_SETTINGS,
        )


class TestSettingsKeyCollection(SimpleTestCase):

    class _PluralPets(SettingsKeyCollection):
        CAT = "cats"
        DOG = "dogs"
        PIG = "pigs"
        FISH = "fish"

    PluralPets = _PluralPets()

    def test___repr__(self):
        self.assertEqual(
            f"<_PluralPets values={self.PluralPets._values}>",
            repr(self.PluralPets),
        )

    def test___contains__(self):
        self.assertTrue("pigs" in self.PluralPets)

    def test_not__contains__(self):
        self.assertFalse("viper" in self.PluralPets)

    def test___iter__(self):
        self.assertEqual(
            ["cats", "dogs", "fish", "pigs"],
            sorted(self.PluralPets)
        )
