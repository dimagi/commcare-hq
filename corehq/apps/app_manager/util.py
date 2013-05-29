import functools
from django.core.cache import cache
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
    cache_key = 'get_case_properties-%s-%s' % (app.get_id, ','.join(case_types))
    value = cache.get(cache_key)
    if value:
        return value

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

    value = dict(
        (case_type, sorted(get_properties(case_type)))
        for case_type in case_types
    )

    cache.set(cache_key, value, 5*60)
    return value