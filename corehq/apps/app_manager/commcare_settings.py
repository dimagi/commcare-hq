from collections import defaultdict
from django.utils.translation import ugettext_noop
import os
import yaml


def load_custom_commcare_settings():
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    settings = []
    with open(os.path.join(path,
                           'commcare-profile-settings.yaml')) as f:
        for setting in yaml.load(f):
            if not setting.get('type'):
                setting['type'] = 'properties'
            settings.append(setting)

    with open(os.path.join(path, 'commcare-app-settings.yaml')) as f:
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


def load_commcare_settings_layout(doc_type):
    settings = dict([
        ('{0}.{1}'.format(setting.get('type'), setting.get('id')), setting)
        for setting in load_custom_commcare_settings()
    ])
    path = os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'json')
    with open(os.path.join(path, 'commcare-settings-layout.yaml')) as f:
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

SETTINGS = load_custom_commcare_settings()

LAYOUT = dict(
    (doc_type, load_commcare_settings_layout(doc_type))
    for doc_type in ('Application', 'RemoteApp')
)

SETTINGS_LOOKUP = defaultdict(lambda: defaultdict(dict))
for setting in SETTINGS:
    SETTINGS_LOOKUP[setting['type']][setting['id']] = setting