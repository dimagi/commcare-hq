from collections import defaultdict
import re

from corehq.apps.app_manager.util import get_app_manager_template
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop
import os
import yaml


def _load_custom_commcare_settings(domain=None):
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    settings = []
    with open(os.path.join(
            path,
            get_app_manager_template(
                domain,
                'v1/commcare-profile-settings.yaml',
                'v2/commcare-profile-settings.yaml'
            )
    )) as f:
        for setting in yaml.load(f):
            if not setting.get('type'):
                setting['type'] = 'properties'
            settings.append(setting)

    with open(os.path.join(path, get_app_manager_template(
        domain,
        'v1/commcare-app-settings.yaml',
        'v2/commcare-app-settings.yaml'
    ))) as f:
        for setting in yaml.load(f):
            if not setting.get('type'):
                setting['type'] = 'hq'
            settings.append(setting)
    for setting in settings:
        if not setting.get('widget'):
            setting['widget'] = 'select'
        # i18n; not statically analyzable
        setting['name'] = ugettext_noop(setting['name'])
    return settings


def _load_commcare_settings_layout(doc_type, domain):
    settings = dict([
        ('{0}.{1}'.format(setting.get('type'), setting.get('id')), setting)
        for setting in _load_custom_commcare_settings(domain)
    ])
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    with open(os.path.join(
            path,
            get_app_manager_template(
                domain,
                'v1/commcare-settings-layout.yaml',
                'v2/commcare-settings-layout.yaml'
            ))) as f:
        layout = yaml.load(f)

    for section in layout:
        # i18n; not statically analyzable
        section['title'] = ugettext_noop(section['title'])
        for i, key in enumerate(section['settings']):
            setting = settings.pop(key)
            if doc_type == 'Application' or setting['type'] == 'hq':
                section['settings'][i] = setting
            else:
                section['settings'][i] = None
        section['settings'] = filter(None, section['settings'])
        for setting in section['settings']:
            setting['value'] = None

    if settings:
        raise Exception(
            "CommCare settings layout should mention "
            "all the available settings. "
            "The following settings went unmentioned: %s" % (
                ', '.join(settings.keys())
            )
        )
    return layout


@memoized
def get_custom_commcare_settings():
    return _load_custom_commcare_settings()


@memoized
def get_commcare_settings_layout(domain):
    layout = {
        doc_type: _load_commcare_settings_layout(doc_type, domain)
        for doc_type in ('Application', 'RemoteApp', 'LinkedApplication')
    }
    layout.update({'LinkedApplication': {}})
    return layout


@memoized
def get_commcare_settings_lookup():
    settings_lookup = defaultdict(lambda: defaultdict(dict))
    for setting in get_custom_commcare_settings():
        settings_lookup[setting['type']][setting['id']] = setting
    return settings_lookup


def parse_condition_string(condition_str):
    pattern = re.compile("{(?P<type>[\w-]+?)\.(?P<id>[\w-]+?)}=(?P<equals>true|false|'[\w-]+')")
    match = pattern.match(condition_str).groupdict()
    if match["equals"] == 'true':
        match["equals"] = True
    elif match["equals"] == 'false':
        match["equals"] = False
    elif len(match["equals"]) > 1 and match["equals"][0] is "'" and match["equals"][-1] is "'":
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
