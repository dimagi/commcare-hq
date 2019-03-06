from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django_prbac.utils import has_privilege as prbac_has_privilege
from django.utils.translation import ugettext_lazy as _

from corehq import feature_previews, toggles
from corehq.apps.app_manager.exceptions import AddOnNotFoundException
from corehq.apps.app_manager.models import Module, AdvancedModule, ShadowModule
from corehq.apps.domain.models import Domain
from corehq.privileges import LOOKUP_TABLES


# Similar to feature flags and/or feature previews, but specific to an individual application
# and with the additional notion of a feature being "in use" in a specific module or form
# even if the add-on isn't enabled.
class AddOn(object):
    def __init__(self, name, description, help_link=None, privilege=None, used_in_module=None, used_in_form=None):
        self.name = name
        self.description = description
        self.help_link = help_link
        self.privilege = privilege

        self.used_in_module = used_in_module if used_in_module else lambda m: False
        self.used_in_form = used_in_form if used_in_form else lambda f: False

    def has_privilege(self, request):
        if not self.privilege:
            return True
        return prbac_has_privilege(request, self.privilege)


def _uses_case_list_menu_item(module):
    if getattr(module, 'case_list', False) and module.case_list.show:
        return True
    if getattr(module, 'task_list', False) and module.task_list.show:
        return True
    if getattr(module, 'referral_list', False) and module.referral_list.show:
        return True
    return False


def _uses_conditional_form_actions(form):
    if form.form_type != 'module_form':
        # Don't bother restricting non-basic forms
        return True
    return form.actions.open_case.condition.type == 'if' or form.actions.close_case.condition.type == 'if'


def _uses_detail_format(module, column_format):
    details = []
    if isinstance(module, Module) or isinstance(module, ShadowModule):
        details = [module.case_details, module.ref_details]
    elif isinstance(module, AdvancedModule):
        details = [module.case_details, module.product_details]
    return any([c.format for d in details for c in d.short.columns + d.long.columns if c.format == column_format])


def _uses_calculated_property(module):
    def _column_is_calculated_property(col):
        return col.useXpathExpression
    return hasattr(module, 'case_details') and (
        any(_column_is_calculated_property(column) for column in module.case_details.short.columns)
        or any(_column_is_calculated_property(column) for column in module.case_details.long.columns)
    )


# Apps that were created before add-ons were released get the original set of add-ons enabled
# automatically, so they wouldn't get functionality suddenly turned off during the release.
def _grandfathered(slug, app):
    if app.add_ons:
        return False

    release_date = datetime(2017, 7, 31, 20)
    if slug not in [
        "conditional_form_actions", "subcases", "case_list_menu_item", "enum_image", "menu_mode",
        "register_from_case_list", "display_conditions", "conditional_enum", "calc_xpaths",
        "advanced_itemsets", "case_detail_overwrite",
    ]:
        return False
    domain_obj = Domain.get_by_name(app.domain)
    return (getattr(domain_obj, 'date_created') or datetime(2000, 1, 1)) < release_date


_ADD_ONS = {
    "advanced_itemsets": AddOn(
        name=feature_previews.VELLUM_ADVANCED_ITEMSETS.label,
        description=feature_previews.VELLUM_ADVANCED_ITEMSETS.description,
        privilege=LOOKUP_TABLES,
    ),
    "calc_xpaths": AddOn(
        name=feature_previews.CALC_XPATHS.label,
        description=feature_previews.CALC_XPATHS.description,
        used_in_module=_uses_calculated_property,
        help_link=feature_previews.CALC_XPATHS.help_link,
    ),
    "case_detail_overwrite": AddOn(
        name=_("Case Detail Overwrite"),
        description=_("Ability to overwrite one case list or detail's settings with another's. "
        "Available in menu settings, in the actions tab."),
    ),
    "case_list_menu_item": AddOn(
        name=_("Case List Menu Item"),
        description=_("Allows the mobile user to view the case list and case details without actually opening "
        "a form. Available in menu settings."),
        used_in_module=lambda m: _uses_case_list_menu_item(m),
    ),
    "conditional_enum": AddOn(
        name=feature_previews.CONDITIONAL_ENUM.label,
        description=feature_previews.CONDITIONAL_ENUM.description,
        used_in_module=lambda m: _uses_detail_format(m, 'conditional-enum'),
    ),
    "conditional_form_actions": AddOn(
        name=_('Case Conditions'),
        description=_("Open or close a case only if a specific question has a particular answer. "
        "Available in form settings, under Case Management."),
        help_link="https://confluence.dimagi.com/display/commcarepublic/Case+Configuration",
        used_in_form=lambda f: _uses_conditional_form_actions(f)
    ),
    "display_conditions": AddOn(
        name=_("Display Conditions"),
        description=_("Write logic to show or hide forms and menus on the mobile device. "
        "Available in form and menu settings."),
        help_link="https://confluence.dimagi.com/display/commcarepublic/Application+Design",
        used_in_form=lambda f: bool(getattr(f, 'form_filter', False)),
        used_in_module=lambda m: bool(m.module_filter),
    ),
    "enum_image": AddOn(
        name=feature_previews.ENUM_IMAGE.label,
        description=feature_previews.ENUM_IMAGE.description,
        help_link=feature_previews.ENUM_IMAGE.help_link,
        used_in_module=lambda m: _uses_detail_format(m, 'enum-image'),
    ),
    "menu_mode": AddOn(
        name=_("Menu Mode"),
        description=_("Control whether a form's enclosing menu is displayed on the mobile device or not. "
        "Available in menu settings."),
        used_in_module=lambda m: getattr(m, 'put_in_root', False),
    ),
    "register_from_case_list": AddOn(
        name=_("Register from case list"),
        description=_("Minimize duplicates by making registration forms available directly from the case list "
        "on the mobile device. Availabe in menu settings."),
        help_link="https://confluence.dimagi.com/pages/viewpage.action?pageId=30605985",
        used_in_module=lambda m: m.case_list_form.form_id,
    ),
    "subcases": AddOn(
        name=_("Child Cases"),
        description=_("Open other types of cases, linking them to the case that "
        "created them. Available in form settings."),
        help_link="https://confluence.dimagi.com/display/commcarepublic/Child+Cases",
        used_in_form=lambda f: f.form_type != "module_form" or bool(f.actions.subcases),
    ),
    "empty_case_lists": AddOn(
        name=_("New Case Lists Created Empty"),
        description=_("When adding a new case list, don't include a registration and followup form."),
    ),
}

_LAYOUT = [
    {
        "slug": "case_management",
        "collapse": False,
        "name": _("Case Management"),
        "description": _("Build more complex workflows"),
        "slugs": ["conditional_form_actions", "empty_case_lists", "subcases"],
    },
    {
        "slug": "mobile",
        "collapse": True,
        "name": _("Mobile Experience"),
        "description": _("Improve the user experience of your mobile workers"),
        "slugs": [
            "case_list_menu_item",
            "enum_image",
            "menu_mode",
            "register_from_case_list",
        ],
    },
    {
        "slug": "xpath",
        "collapse": True,
        "name": _("Calculations"),
        "description": _("Add logic to your app with XPath expressions"),
        "slugs": ["display_conditions", "conditional_enum", "calc_xpaths", "advanced_itemsets"],
    },
    {
        "slug": "efficiency",
        "collapse": True,
        "name": _("App Building Efficiency"),
        "description": _("Tools to help build your apps faster"),
        "slugs": ["case_detail_overwrite"],
    },
]


# Determine whether or not UI should show a feature, based on
# availability and whether or not it's in use.
def show(slug, request, app, module=None, form=None):
    if slug not in _ADD_ONS:
        raise AddOnNotFoundException(slug)
    add_on = _ADD_ONS[slug]

    # Do not show if there's a required privilege missing
    if not add_on.has_privilege(request):
        return False

    # Show if flag to enable all toggles is on
    if toggles.ENABLE_ALL_ADD_ONS.enabled_for_request(request):
        return True

    if _grandfathered(slug, app):
        return True

    # Show if add-on has been enabled for app
    show = slug in app.add_ons and app.add_ons[slug]

    # Show if add-on is also a feature preview this domain has on
    # (that has not been turned off for this app specifically)
    if slug not in app.add_ons:
        previews = feature_previews.previews_dict(app.domain)
        if slug in previews:
            show = show or previews[slug]

    # Show if add-on is being used by the current form/module
    if form:
        show = show or add_on.used_in_form(form)
    elif module:
        show = show or add_on.used_in_module(module)

    return show


# Get a slug => bool dictionary signifying which add-ons to display in UI
def get_dict(request, app, module=None, form=None):
    init_app(request, app)
    return {slug: show(slug, request, app, module, form) for slug in _ADD_ONS.keys()}


# Get add-ons for display in settings UI
def get_layout(request):
    all_slugs = set(_ADD_ONS.keys())
    layout_slugs = set([slug for section in _LAYOUT for slug in section['slugs']])
    if all_slugs != layout_slugs:
        difference = ", ".join(all_slugs ^ layout_slugs)
        if all_slugs - layout_slugs:
            raise AddOnNotFoundException("Add-ons not in layout: {}".format(difference))
        raise AddOnNotFoundException("Add-ons in layout do not exist: {}".format(difference))
    return [dict({'add_ons': [{
        'slug': slug,
        'name': _ADD_ONS[slug].name,
        'description': _ADD_ONS[slug].description,
        'help_link': _ADD_ONS[slug].help_link,
    } for slug in section['slugs'] if _ADD_ONS[slug].has_privilege(request)]}, **section) for section in _LAYOUT]


# Lazily migrate an app that doesn't have any add_ons configured yet.
# Turns on any add-ons that map to feature previews, leaves the rest off.
def init_app(request, app):
    if app.add_ons:
        return

    # Don't use previews_dict because it doesn't include disabled previews
    previews = {p.slug: p.enabled(app.domain) for p in feature_previews.all_previews()}

    for slug in _ADD_ONS.keys():
        add_on = _ADD_ONS[slug]
        enable = False
        if add_on.has_privilege(request):
            # Enable if it's an enabled preview
            if slug in previews:
                enable = previews[slug]

            # Turn on if it's used anywhere
            enable = enable or any([add_on.used_in_module(m) for m in app.modules])
            enable = enable or any([add_on.used_in_form(f) for m in app.modules for f in m.forms])

            enable = enable or _grandfathered(slug, app)
        app.add_ons[slug] = enable
