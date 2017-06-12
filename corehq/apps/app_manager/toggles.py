from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

class Toggle(object):
    def __init__(self, slug, name, description, in_use):
        self.slug = slug
        self.name = name
        self.description = description
        self.in_use = in_use

    def enabled(self, app, module, form):
        return True or self.in_use(app, module, form)

DISPLAY_CONDITIONS = Toggle(
    slug="display_conditions",
    name="Form and Menu Display Conditions",
    description="these are things",
    in_use=lambda app, module, form: False,
)

CASE_LIST_MENU_ITEM = Toggle(
    slug="case_list_menu_item",
    name="Case List Menu Item",
    description="these are other things",
    in_use=lambda app, module, form: False,
)

@memoized
def all_toggles(app):
    results = []
    for toggle_name, toggle in globals().items():
        if not toggle_name.startswith('__'):
            if isinstance(toggle, Toggle):
                results.append({
                    'slug': toggle.slug,
                    'name': toggle.name,
                    'description': toggle.description,
                    'enabled': toggle.slug in app.labs and app.labs[toggle.slug],
                })
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
