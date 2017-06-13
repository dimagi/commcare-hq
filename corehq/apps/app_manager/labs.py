from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.app_manager.models import Module

class Lab(object):
    def __init__(self, slug, name, description, used_in_module=None, used_in_form=None):
        self.slug = slug
        self.name = name
        self.description = description

        self.used_in_module = used_in_module if used_in_module else lambda m: False
        self.used_in_form = used_in_form if used_in_form else lambda f: False

DISPLAY_CONDITIONS = Lab(
    slug="display_conditions",
    name="Form and Menu Display Conditions",
    description="TODO",
    used_in_form=lambda f: bool(f.form_filter),
    used_in_module=lambda m: bool(m.module_filter),
)

CASE_LIST_MENU_ITEM = Lab(
    slug="case_list_menu_item",
    name="Case List Menu Item",
    description="TODO",
    used_in_module=lambda m: isinstance(m, Module) and m.case_list.show,
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
                show = enabled = lab.slug in app.labs and app.labs[lab.slug]
                if form:
                    show = show or lab.used_in_form(form)
                elif module:
                    show = show or lab.used_in_module(module)
                results[lab.slug] = {
                    'slug': lab.slug,
                    'name': lab.name,
                    'description': lab.description,
                    'enabled': enabled,
                    'show': show,
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
