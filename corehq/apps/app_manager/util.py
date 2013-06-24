import functools
from corehq.apps.app_manager.xform import XForm, XFormError, parse_xml
import re
from dimagi.utils.decorators.memoized import memoized


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


def get_case_properties(app, case_types, defaults=()):
    case_types = sorted(case_types)

    # unfortunate, but biggest speed issue is accessing couchdbkit properties
    # so compute them once
    forms_info = []
    for module in app.get_modules():
        for form in module.get_forms():
            forms_info.append((module.case_type, form.actions))

    @memoized
    def get_properties(case_type, already_visited=()):
        if case_type in already_visited:
            return ()

        get_properties_recursive = functools.partial(
            get_properties,
            already_visited=already_visited + (case_type,)
        )

        case_properties = set(defaults)
        parent_types = set()

        for m_case_type, f_actions in forms_info:
            if m_case_type == case_type:
                case_properties.update(
                    f_actions.update_case.update.keys()
                )
            for subcase in f_actions.subcases:
                if subcase.case_type == case_type:
                    case_properties.update(
                        subcase.case_properties.keys()
                    )
                    parent_types.add(m_case_type)

        for parent_type in parent_types:
            for property in get_properties_recursive(parent_type):
                case_properties.add('parent/%s' % property)

        return case_properties

    return dict(
        (case_type, sorted(get_properties(case_type)))
        for case_type in case_types
    )


def get_all_case_properties(app):
    return get_case_properties(
        app,
        set(m.case_type for m in app.modules),
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
    if hasattr(app, 'custom_suite'):
        hq_settings.update({'custom_suite': app.custom_suite})

    hq_settings['build_spec'] = app.build_spec.to_string()

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
