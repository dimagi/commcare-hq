from django import template

from corehq.apps.app_manager.models import ReportModule

register = template.Library()


@register.filter
def get_available_modules_for_case_list_configuration(app, module):
    # necessary to instantiate these because the class attributes are jsonobject.StringProperty's
    # that don't support equality checks
    disallowed_module_types = (ReportModule().module_type,)
    return [
        m for m in app.get_modules()
        if (m.unique_id != module.unique_id
            and m.module_type not in disallowed_module_types
            and m.case_type == module.case_type)
    ]


@register.filter
def get_available_modules_for_case_tile_configuration(app, exclude_module):
    valid_modules = get_available_modules_for_case_list_configuration(app, exclude_module)
    return [m for m in valid_modules
            if m.case_details.short.case_tile_template or m.case_details.short.custom_xml]
