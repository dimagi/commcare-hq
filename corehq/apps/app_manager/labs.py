from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

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
    description="these are things",
    in_use=display_conditions_in_use,
)

CASE_LIST_MENU_ITEM = Lab(
    slug="case_list_menu_item",
    name="Case List Menu Item",
    description="these are other things",
    in_use=lambda app, module, form: False,
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
Display conditions, for both forms and modules
Case list menu item
Registration from case list
Ability to delete registration forms
Ability to overwrite case list/detail with another module's case list/detail
Menu mode (display menu & forms / display only forms)
Conditional case opening/closing (in form's case management, open/close case "Only if the answer to...")
Child cases
Ability to change the case action of a form ("This form does not use cases", etc.)
Icons in Case List
Custom Single and Multiple Answer Questions
Custom Calculations in Case List
'''
