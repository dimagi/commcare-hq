from collections import namedtuple
from django.utils.translation import ugettext_lazy as _

from dimagi.utils.decorators.memoized import memoized

from corehq import feature_previews
from corehq.apps.app_manager.exceptions import LabNotFoundException
from corehq.apps.app_manager.models import Module

class Lab(object):
    def __init__(self, name, description, used_in_module=None, used_in_form=None):
        self.name = name
        self.description = description

        self.used_in_module = used_in_module if used_in_module else lambda m: False
        self.used_in_form = used_in_form if used_in_form else lambda f: False

_LABS = {
    "advanced_itemsets": Lab(
        name=feature_previews.VELLUM_ADVANCED_ITEMSETS.label,
        description=feature_previews.VELLUM_ADVANCED_ITEMSETS.description,
        #used_in_form=TODO
        #privilege=LOOKUP_TABLES,   # TODO
    ),
    "calc_xpaths": Lab(
        name=feature_previews.CALC_XPATHS.label,
        description=feature_previews.CALC_XPATHS.description,
        #used_in_module=TODO
    ),
    "case_detail_overwrite": Lab(
        name=_("Case Detail Overwrite"),
        description=_("Ability to overwrite one case list or detail's settings with another's"),
    ),
    "case_list_menu_item": Lab(
        name=_("Case List Menu Item"),
        description=_("TODO"),
        used_in_module=lambda m: isinstance(m, Module) and (m.case_list.show or m.task_list.show),  # TODO: will this break anything?
    ),
    "conditional_enum": Lab(
        name=feature_previews.CONDITIONAL_ENUM.label,
        description=feature_previews.CONDITIONAL_ENUM.description,
        #used_in_module=TODO
    ),
    "conditional_form_actions": Lab(
        name=_('Allow opening or closing bases based on a condition ("Only if the answer to...")'),
        description=_("Allow changing form actions, deleting registration forms (TODO: rephrase?)"),
        used_in_form=lambda f: f.actions.open_case.condition.type == 'if' or f.actions.close_case.condition.type, # TODO: will this break advanced forms?
    ),
    "display_conditions": Lab(
        name=_("Form and Menu Display Conditions"),
        description=_("TODO"),
        used_in_form=lambda f: bool(f.form_filter),
        used_in_module=lambda m: bool(m.module_filter),
    ),
    "edit_form_actions": Lab(
        name=_("Editing Form Actions"),
        description=_("Allow changing form actions and deleting registration forms"),
    ),
    "enum_image": Lab(
        name=feature_previews.ENUM_IMAGE.label,
        description=feature_previews.ENUM_IMAGE.description,
        #used_in_module=TODO
    ),
    "menu_mode": Lab(
        name=_("Menu Mode"),
        description=_("TODO"),
        used_in_module=lambda m: m.put_in_root,
    ),
    "register_from_case_list": Lab(
        name=_("Register from case list"),
        description=_("TODO"),
        used_in_module=lambda m: m.case_list_form.form_id, # TODO: break anything?
    ),
    "subcases": Lab(
        name=_("Child Cases"),
        description=_("TODO"),
        used_in_form=lambda f: bool(f.actions.subcases),    # TODO: will this break anything?
    ),
    "unstructured_case_lists": Lab(
        name=_("Customize Case List Registration"),
        description=_("Create new case lists without a registration form, and allow deletion of registration forms."),
    ),
}

@memoized
def get(slug, app, module=None, form=None):
    if slug not in _LABS:
        raise LabNotFoundException(slug)
    lab = _LABS[slug]
    enabled = slug in app.labs and app.labs[slug]

    previews = feature_previews.previews_dict(app.domain)
    if slug in previews:
        enabled = enabled or previews[slug]

    show = enabled
    if form:
        show = show or lab.used_in_form(form)
    elif module:
        show = show or lab.used_in_module(module)
    return {
        'slug': slug,
        'name': lab.name,
        'description': lab.description,
        'enabled': enabled,
        'show': show,
    }

@memoized
def get_all(app, module=None, form=None):
    results = {}
    for slug, lab in _LABS.items():
        results[slug] = get(slug, app, module, form)
    return results
