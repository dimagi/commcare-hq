"""Elasticsearch index tuning parameters configurable in Django settings.

Changes to the constant values (settings keys, default values, etc) in this
module require forum announcements for downstream self-hosters.
"""

import warnings
from functools import cached_property

from django.conf import settings


def render_index_tuning_settings(index_settings_key):
    """Returns an index tuning settings dict for the provided index settings
    key. The returned values are rendered from four increasingly specific
    sources using a last-set-wins algorithm. Values are set in order:

    1. Values of ``DEFAULT_TUNING_SETTINGS[DEFAULT]`` from this module.
    2. Values of ``DEFAULT_TUNING_SETTINGS[index_settings_key]`` from this
       module (if present).
    3. Values of ``ES_SETTINGS[DEFAULT]`` from Django settings (if present).
    4. Values of ``ES_SETTINGS[index_settings_key]`` from Django settings (if
       present).

    Any settings whose value is the special ``REMOVE_SETTING`` value will be
    removed from the rendered dictionary unless re-set by a subsequent, more
    specific source.

    An ``InvalidTuningSettingsError`` exception is raised if any index settings
    keys exist which are not a member of ``IndexTuningKey``. For example, if
    ``settings.ES_SETTINGS[DEFAULT] == {"answer": 42}`` then this function will
    raise because ``answer`` is not an ``IndexTuningKey`` member.

    A warning is issued if ``index_settings_key`` is not one of the
    ``IndexSettingsKey`` collection.

    :param index_settings_key: A key in Django ``settings.ES_SETTINGS``
        dictionary to use when rendering the settings.
    :raises: ``InvalidTuningSettingsError``
    """
    if index_settings_key not in IndexSettingsKey:
        msg = (f"Invalid index settings key {index_settings_key!r}, "
               f"expected one of {sorted(IndexSettingsKey)}")
        warnings.warn(msg, UserWarning)
    tuning_settings = {}
    valid_tuning_keys = set(IndexTuningKey)
    for collection in [DEFAULT_TUNING_SETTINGS, settings.ES_SETTINGS or {}]:
        for settings_key in [DEFAULT, index_settings_key]:
            settings_values = collection.get(settings_key, {})
            invalid_settings = set(settings_values) - valid_tuning_keys
            if invalid_settings:
                if collection is DEFAULT_TUNING_SETTINGS:
                    where = f"{__name__}.DEFAULT_TUNING_SETTINGS"
                else:
                    where = "django.conf.settings.ES_SETTINGS"
                msg = (f"Found invalid Elastic index tuning settings for "
                       f"{where}[{settings_key!r}]: {invalid_settings}")
                raise InvalidTuningSettingsError(msg)
            for tunable in valid_tuning_keys:
                try:
                    value = settings_values[tunable]
                except KeyError:
                    continue
                if value is REMOVE_SETTING:
                    del tuning_settings[tunable]
                else:
                    tuning_settings[tunable] = value
    return tuning_settings


class InvalidTuningSettingsError(Exception):
    pass


class SettingsKeyCollection:
    """An Enum-like collection of values used to reference Elastic index tuning
    configurations in Django settings.

    An ``enum.Enum`` subclass was not used because it is not well suited for
    this task. That is to say: consumers of this type only wish to compare
    *string values*, and converting values to/from ``str`` and "enum member"
    would add unnecessary type cruft to the implementation without much (if any)
    added value. While investigating this option, it also turns out that Python
    does not have a ``StrEnum`` type until version 3.11.
    """

    @cached_property
    def _values(self):
        """Returns a set of class attribute values whose:
        - attribute name does not start with an underscore (``_``)
        - value is a string
        """
        values = set()
        for key, value in type(self).__dict__.items():
            if not key.startswith("_") and type(value) is str:
                values.add(value)
        return values

    def __repr__(self):
        return f"<{type(self).__name__} values={self._values}>"

    def __contains__(self, value):
        return value in self._values

    def __iter__(self):
        yield from self._values


class _IndexSettingsKey(SettingsKeyCollection):
    APPS = "hqapps"
    CASES = "hqcases"
    CASE_SEARCH = "case_search"
    DOMAINS = "hqdomains"
    FORMS = "xforms"
    GROUPS = "hqgroups"
    SMS = "smslogs"
    USERS = "hqusers"


class _IndexTuningKey(SettingsKeyCollection):
    REPLICAS = "number_of_replicas"
    SHARDS = "number_of_shards"


IndexSettingsKey = _IndexSettingsKey()
IndexTuningKey = _IndexTuningKey()


# Allow removing settings from defaults by setting the value to this constant in
# settings.ES_SETTINGS.
# TODO: change this constant to an object that isn't actually a meaningful
# (e.g. `__do_not_set__`) instead of `None` (because `None` is how you revert a
# setting to the value the server is configured to use).
REMOVE_SETTING = None

DEFAULT = "default"

DEFAULT_REPLICAS = 0
DEFAULT_SHARDS = 5

DEFAULT_TUNING_SETTINGS = {
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
}
