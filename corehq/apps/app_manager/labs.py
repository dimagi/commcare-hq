from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.app_manager.models import Module

class Lab(object):
    def __init__(self, slug, name, description, in_use):
        self.slug = slug
        self.name = name
        self.description = description
        self.in_use = in_use

    def enabled(self, app, module, form):
        return True or self.in_use(app, module, form)

def display_conditions_in_use(app, module=None, form=None):
    if form:
        return bool(form.form_filter)
    if module:
        return bool(module.module_filter)
    return False

DISPLAY_CONDITIONS = Lab(
    slug="display_conditions",
    name="Form and Menu Display Conditions",
    description="TODO",
    in_use=display_conditions_in_use,
)

def case_list_menu_item_in_use(app, module=None, form=None):
    if form:
        return False
    if module:
        return isinstance(module, Module) and module.case_list.show
    return False

CASE_LIST_MENU_ITEM = Lab(
    slug="case_list_menu_item",
    name="Case List Menu Item",
    description="TODO",
    in_use=case_list_menu_item_in_use,
)

@memoized
def labs_by_name(app, slug):
    return {t['slug']: t for t in all_labs(app)}

@memoized
def all_labs(app, module=None, form=None):
    results = {}
    for name, lab in globals().items():
        if not name.startswith('__'):
            if isinstance(lab, Lab):
                enabled = lab.slug in app.labs and app.labs[lab.slug]
                results[lab.slug] = {
                    'slug': lab.slug,
                    'name': lab.name,
                    'description': lab.description,
                    'enabled': enabled,
                    'show': enabled or lab.in_use(app, module, form),
                }
    return results




'''
Case list menu item
Registration from case list
Ability to delete registration forms
Ability to overwrite case list/detail with another module's case list/detail
Menu mode (display menu & forms / display only forms)
Conditional case opening/closing (in form's case management, open/close case "Only if the answer to...")
Child cases
Ability to change the case action of a form ("This form does not use cases", etc.)

FEATURE PREVIEWS
Conditional Enum in Case List
Custom Calculations in Case List
Custom Single and Multiple Answer Questions
Icons in Case List
'''
