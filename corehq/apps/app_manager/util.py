import functools
import json
import itertools
from corehq.apps.app_manager.xform import XForm, XFormError, parse_xml
import re
from dimagi.utils.decorators.memoized import memoized
from django.core.cache import cache


def get_app_id(form):
    """
    Given an XForm instance, try to grab the app id, returning
    None if not available. This is just a shortcut since the app_id
    might not always be set.
    """
    return getattr(form, "app_id", None)


def split_path(path):
    path_parts = path.split('/')
    name = path_parts.pop(-1)
    path = '/'.join(path_parts)
    return path, name


def save_xform(app, form, xml):
    try:
        xform = XForm(xml)
    except XFormError:
        pass
    else:
        duplicates = app.get_xmlns_map()[xform.data_node.tag_xmlns]
        for duplicate in duplicates:
            if form == duplicate:
                continue
            else:
                data = xform.data_node.render()
                xmlns = "http://openrosa.org/formdesigner/%s" % form.get_unique_id()
                data = data.replace(xform.data_node.tag_xmlns, xmlns, 1)
                xform.instance_node.remove(xform.data_node.xml)
                xform.instance_node.append(parse_xml(data))
                xml = xform.render()
                break
    form.source = xml

CASE_TYPE_REGEX = r'^[\w-]+$'
_case_type_regex = re.compile(CASE_TYPE_REGEX)

def is_valid_case_type(case_type):
    """
    >>> is_valid_case_type('foo')
    True
    >>> is_valid_case_type('foo-bar')
    True
    >>> is_valid_case_type('foo bar')
    False
    >>> is_valid_case_type('')
    False
    >>> is_valid_case_type(None)
    False
    """
    return bool(_case_type_regex.match(case_type or ''))


class ParentCasePropertyBuilder(object):
    def __init__(self, app, defaults=()):
        self.app = app
        self.defaults = defaults

    @property
    @memoized
    def forms_info(self):
        # unfortunate, but biggest speed issue is accessing couchdbkit properties
        # so compute them once

        forms_info = []
        for module in self.app.get_modules():
            for form in module.get_forms():
                forms_info.append((module.case_type, form))
        return forms_info

    @memoized
    def get_parent_types_and_contributed_properties(self, case_type):
        parent_types = set()
        case_properties = set()
        for m_case_type, form in self.forms_info:
            p_types, c_props = form.get_parent_types_and_contributed_properties(m_case_type, case_type)
            parent_types.update(p_types)
            case_properties.update(c_props)
        return parent_types, case_properties

    def get_parent_types(self, case_type):
        parent_types, _ = \
            self.get_parent_types_and_contributed_properties(case_type)
        return set(p[0] for p in parent_types)

    @memoized
    def get_properties(self, case_type, already_visited=()):
        if case_type in already_visited:
            return ()

        get_properties_recursive = functools.partial(
            self.get_properties,
            already_visited=already_visited + (case_type,)
        )

        case_properties = set(self.defaults)

        for m_case_type, form in self.forms_info:
            case_properties.update(form.get_case_updates(case_type))

        parent_types, contributed_properties = \
            self.get_parent_types_and_contributed_properties(case_type)
        case_properties.update(contributed_properties)
        for parent_type in parent_types:
            for property in get_properties_recursive(parent_type[0]):
                case_properties.add('%s/%s' % (parent_type[1], property))

        return case_properties

    def get_case_property_map(self, case_types):
        case_types = sorted(case_types)
        return dict(
            (case_type, sorted(self.get_properties(case_type)))
            for case_type in case_types
        )


def get_case_properties(app, case_types, defaults=()):
    builder = ParentCasePropertyBuilder(app, defaults)
    return builder.get_case_property_map(case_types)


def get_all_case_properties(app):
    return get_case_properties(
        app,
        set(itertools.chain.from_iterable(m.get_case_types() for m in app.modules)),
        defaults=('name',)
    )


def get_settings_values(app):
    try:
        profile = app.profile
    except AttributeError:
        profile = {}
    hq_settings = dict([
        (attr, app[attr])
        for attr in app.properties() if not hasattr(app[attr], 'pop')
    ])
    if getattr(app, 'use_custom_suite', False):
        hq_settings.update({'custom_suite': getattr(app, 'custom_suite', None)})

    hq_settings['build_spec'] = app.build_spec.to_string()
    # the admin_password hash shouldn't be sent to the client
    hq_settings.pop('admin_password', None)

    return {
        'properties': profile.get('properties', {}),
        'features': profile.get('features', {}),
        'hq': hq_settings,
        '$parent': {
            'doc_type': app.get_doc_type(),
            '_id': app.get_id,
            'domain': app.domain,
        }
    }


def add_odk_profile_after_build(app_build):
    """caller must save"""

    profile = app_build.create_profile(is_odk=True)
    app_build.lazy_put_attachment(profile, 'files/profile.ccpr')
    # hack this in for records
    app_build.odk_profile_created_after_build = True


def create_temp_sort_column(field, index):
    """
    Used to create a column for the sort only properties to
    add the field to the list of properties and app strings but
    not persist anything to the detail data.
    """
    from corehq.apps.app_manager.models import SortOnlyDetailColumn
    return SortOnlyDetailColumn(
        model='case',
        field=field,
        format='invisible',
        header=None,
    )


def is_sort_only_column(column):
    from corehq.apps.app_manager.models import SortOnlyDetailColumn
    return isinstance(column, SortOnlyDetailColumn)


def get_correct_app_class(doc):
    from corehq.apps.app_manager.models import Application, RemoteApp
    return {
        'Application': Application,
        'Application-Deleted': Application,
        "RemoteApp": RemoteApp,
        "RemoteApp-Deleted": RemoteApp,
    }[doc['doc_type']]


def all_apps_by_domain(domain):
    from corehq.apps.app_manager.models import ApplicationBase
    rows = ApplicationBase.get_db().view(
        'app_manager/applications',
        startkey=[domain, None],
        endkey=[domain, None, {}],
        include_docs=True,
    ).all()
    for row in rows:
        doc = row['doc']
        yield get_correct_app_class(doc).wrap(doc)


def new_careplan_module(app, name, lang, target_module):
    from corehq.apps.app_manager.models import CareplanModule, CareplanGoalForm, CareplanTaskForm
    module = app.add_module(CareplanModule.new_module(
        app,
        name,
        lang,
        target_module.unique_id,
        target_module.case_type)
    )

    forms = [form_class.new_form(lang, name, mode)
                for form_class in [CareplanGoalForm, CareplanTaskForm]
                for mode in ['create', 'update']]

    for form, source in forms:
        module.forms.append(form)
        form = module.get_form(-1)
        form.source = source

    return module


def languages_mapping():
    mapping = cache.get('__languages_mapping')
    if not mapping:
        with open('submodules/langcodes/langs.json') as langs_file:
            lang_data = json.load(langs_file)
            mapping = dict([(l["two"], l["names"]) for l in lang_data])
        mapping["default"] = ["Default Language"]
        cache.set('__languages_mapping', mapping, 12*60*60)
    return mapping
