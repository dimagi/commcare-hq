from django.utils.translation import gettext as _

from lxml import etree

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.suite_xml.xml_models import Suite


def get_select_chain(app, module, include_self=True):
    return [
        module
        for (module, _) in get_select_chain_with_sessions(app, module, include_self=include_self)
    ]


def get_select_chain_with_sessions(app, module, include_self=True):
    select_chain = []
    if include_self:
        if module.is_multi_select():
            select_chain.append((module, 'selected_cases'))
        else:
            select_chain.append((module, 'case_id'))
    previous_module = module
    case_type = module.case_type
    i = len(select_chain)
    while hasattr(previous_module, 'parent_select') and previous_module.parent_select.active:
        is_other_relation = previous_module.parent_select.relationship is None
        current_module = app.get_module_by_unique_id(
            previous_module.parent_select.module_id,
            error=_("Case list used by parent child selection in '{}' not found").format(
                previous_module.default_name()),
        )

        if current_module.is_multi_select():
            session_var = ('parent_' * i) + 'selected_cases'
        elif is_other_relation and case_type == current_module.case_type:
            session_var = 'case_id_' + case_type
        else:
            session_var = ('parent_' * i or 'case_') + 'id'

        if current_module in [m for (m, _) in select_chain]:
            raise SuiteValidationError("Circular reference in case hierarchy")
        select_chain.append((current_module, session_var))

        # update vars for next loop
        previous_module = current_module
        case_type = current_module.case_type
        i += 1
    return select_chain


def get_select_chain_meta(app, module):
    """
        return list of dicts containing datum IDs and case types
        [
           {'session_var': 'parent_parent_id', ... },
           {'session_var': 'parent_id', ...}
           {'session_var': 'child_id', ...},
        ]
    """
    if not (module and module.module_type == 'basic'):
        return []

    select_chain = get_select_chain_with_sessions(app, module)
    return [
        {
            'session_var': session_var,
            'case_type': mod.case_type,
            'module': mod,
            'index': i
        }
        for i, (mod, session_var) in reversed(list(enumerate(select_chain)))
    ]


def validate_suite(suite):
    if isinstance(suite, str):
        suite = suite.encode('utf-8')
    if isinstance(suite, bytes):
        suite = etree.fromstring(suite)
    if isinstance(suite, etree._Element):
        suite = Suite(suite)
    assert isinstance(suite, Suite), \
        'Could not convert suite to a Suite XmlObject: %r' % suite

    def is_unique_list(things):
        return len(set(things)) == len(things)

    for detail in suite.details:
        orders = [field.sort_node.order for field in detail.fields
                  if field and field.sort_node]
        if not is_unique_list(orders):
            raise SuiteValidationError('field/sort/@order must be unique per detail')


def _should_use_root_display(module):
    # child modules set to display only forms should use their parent module's
    # name so as not to confuse mobile when the two are combined
    return module.put_in_root and module.root_module and not module.root_module.put_in_root


def get_module_locale_id(module):
    if _should_use_root_display(module):
        module = module.root_module
    return id_strings.module_locale(module)


def get_form_locale_id(form):
    return id_strings.form_locale(form)


def get_ordered_case_types_for_module(module):
    return get_ordered_case_types(module.case_type, module.additional_case_types)


def get_ordered_case_types(case_type, additional_case_types=None):
    """Utility to provide consistent order of case types in suite files."""
    additional_case_types = additional_case_types or []
    additional_types = set(additional_case_types) - {case_type}
    return [case_type] + sorted(additional_types)


def is_valid_results_instance_name(app, instance_name):
    # avoid circular import
    from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
        RESULTS_INSTANCE,
        RESULTS_INSTANCE_INLINE,
    )

    valid_instance_names = {RESULTS_INSTANCE, RESULTS_INSTANCE_INLINE}
    valid_instance_names.update(module.search_config.get_instance_name()
                                for module in app.get_modules() if hasattr(module, 'search_config'))
    return instance_name in valid_instance_names
