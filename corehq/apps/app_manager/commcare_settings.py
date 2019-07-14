from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
import re

from memoized import memoized
from django.utils.translation import ugettext_noop, ugettext
import os
import yaml
import six
from io import open

from corehq.apps.app_manager.util import app_doc_types
from corehq.util.python_compatibility import soft_assert_type_text

PROFILE_SETTINGS_TO_TRANSLATE = [
    'name',
    'description',
    'value_names',
    'disabled_txt',
    'values_txt',
]

LAYOUT_SETTINGS_TO_TRANSLATE = [
    'title'
]


def _translate_setting(setting, prop):
    value = setting[prop]
    if not isinstance(value, six.string_types):
        return [ugettext(v) for v in value]
    else:
        if six.PY3:
            soft_assert_type_text(value)
        return ugettext(value)


def _load_custom_commcare_settings():
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    settings = []
    with open(os.path.join(path, 'commcare-profile-settings.yaml'), encoding='utf-8') as f:
        for setting in yaml.safe_load(f):
            if not setting.get('type'):
                setting['type'] = 'properties'
            settings.append(setting)

    with open(os.path.join(path, 'commcare-app-settings.yaml'), encoding='utf-8') as f:
        for setting in yaml.safe_load(f):
            if not setting.get('type'):
                setting['type'] = 'hq'
            settings.append(setting)
    for setting in settings:
        if not setting.get('widget'):
            setting['widget'] = 'select'

        for prop in PROFILE_SETTINGS_TO_TRANSLATE:
            if prop in setting:
                setting[prop] = _translate_setting(setting, prop)
    return settings


def _load_commcare_settings_layout(app):
    settings = dict([
        ('{0}.{1}'.format(setting.get('type'), setting.get('id')), setting)
        for setting in _load_custom_commcare_settings()
    ])
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    with open(os.path.join(path, 'commcare-settings-layout.yaml'), encoding='utf-8') as f:
        layout = yaml.safe_load(f)

    doc_type = app.get_doc_type()
    j2me_section_ids = ['app-settings-j2me-properties', 'app-settings-j2me-ui']
    for section in layout:
        # i18n; not statically analyzable
        section['title'] = ugettext_noop(section['title'])
        for i, key in enumerate(section['settings']):
            include = False
            setting = settings.pop(key)
            if doc_type == 'Application':
                include = True
                section['settings'][i] = setting
            elif doc_type == 'LinkedApplication':
                include = setting.get('supports_linked_app', False)
            elif doc_type == 'RemoteApp':
                include = setting['type'] == 'hq'
            else:
                raise Exception("Unexpected doc_type received: %s" % doc_type)
            section['settings'][i] = setting if include else None

        section['settings'] = [_f for _f in section['settings'] if _f]
        for setting in section['settings']:
            setting['value'] = None
            for prop in LAYOUT_SETTINGS_TO_TRANSLATE:
                if prop in setting:
                    setting[prop] = _translate_setting(setting, prop)

        if not app.build_spec.supports_j2me() and section['id'] in j2me_section_ids:
            section['always_show'] = False

    if settings:
        raise Exception(
            "CommCare settings layout should mention "
            "all the available settings. "
            "The following settings went unmentioned: %s" % (
                ', '.join(settings)
            )
        )
    return layout


@memoized
def get_custom_commcare_settings():
    return _load_custom_commcare_settings()


@memoized
def get_commcare_settings_layout(app):
    doc_type = app.get_doc_type()
    if doc_type in app_doc_types():
        return _load_commcare_settings_layout(app)
    raise Exception("Unexpected doc_type received: %s" % doc_type)


@memoized
def get_commcare_settings_lookup():
    settings_lookup = defaultdict(lambda: defaultdict(dict))
    for setting in get_custom_commcare_settings():
        settings_lookup[setting['type']][setting['id']] = setting
    return settings_lookup


def parse_condition_string(condition_str):
    pattern = re.compile(r"{(?P<type>[\w-]+?)\.(?P<id>[\w-]+?)}=(?P<equals>true|false|'[\w-]+')")
    match = pattern.match(condition_str).groupdict()
    if match["equals"] == 'true':
        match["equals"] = True
    elif match["equals"] == 'false':
        match["equals"] = False
    elif len(match["equals"]) > 1 and match["equals"][0] == "'" and match["equals"][-1] == "'":
            match["equals"] = match["equals"][1:-1]
    else:
        raise Exception("Error parsing contingent condition")
    return match


def check_condition(app, condition_str):
    cond = parse_condition_string(condition_str)
    attr_val = app.get_profile_setting(cond["type"], cond["id"])
    return attr_val == cond["equals"] or \
           (cond["equals"] == 'true' and attr_val is True) or (cond["equals"] == 'false' and attr_val is False)


def check_contingent_for_circular_dependency(contingent, yaml_lookup, deps=None):
    deps = deps or []
    cond = parse_condition_string(contingent["condition"])
    dep = "%s.%s" % (cond["type"], cond["id"])
    if dep in deps:
        return True
    deps.append(dep)
    cond_setting = yaml_lookup[cond["type"]][cond["id"]]
    return check_setting_for_circular_dependency(cond_setting, yaml_lookup, deps)


def check_setting_for_circular_dependency(setting, yaml_lookup, deps=None):
    deps = deps or []
    for contingent in setting.get("contingent_default", []):
        if check_contingent_for_circular_dependency(contingent, yaml_lookup, deps):
            return True
    return False


def circular_dependencies(settings, yaml_lookup):
    """
    Checks the settings yaml file for circular dependencies in the contingent_defaults.
    This is here that we can test that SETTINGS has no cycles in our test suite.
    """
    for s in settings:
        if check_setting_for_circular_dependency(s, yaml_lookup):
            return True
    return False
