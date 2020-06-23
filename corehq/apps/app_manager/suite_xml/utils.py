from django.utils.translation import ugettext as _

from lxml import etree

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.suite_xml.xml_models import Suite


def get_select_chain(app, module, include_self=True):
    select_chain = [module] if include_self else []
    current_module = module
    while hasattr(current_module, 'parent_select') and current_module.parent_select.active:
        current_module = app.get_module_by_unique_id(
            current_module.parent_select.module_id,
            error=_("Case list used by parent child selection in '{}' not found").format(
                current_module.default_name()),
        )
        if current_module in select_chain:
            raise SuiteValidationError("Circular reference in case hierarchy")
        select_chain.append(current_module)
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

    select_chain = get_select_chain(app, module)
    return [
        {
            'session_var': ('parent_' * i or 'case_') + 'id',
            'case_type': mod.case_type,
            'module': mod,
            'index': i
        }
        for i, mod in reversed(list(enumerate(select_chain)))
    ]


def validate_suite(suite):
    if isinstance(suite, str):
        suite = suite.encode('utf-8')
    if isinstance(suite, bytes):
        suite = etree.fromstring(suite)
    if isinstance(suite, etree._Element):
        suite = Suite(suite)
    assert isinstance(suite, Suite),\
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
