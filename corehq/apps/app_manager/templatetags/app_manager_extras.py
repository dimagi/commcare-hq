from django import template
from corehq.apps.app_manager.models import ReportModule, CareplanModule


register = template.Library()


@register.filter
def get_available_modules_for_case_list_configuration(app, module):
    # necessary to instantiate these because the class attributes are jsonobject.StringProperty's
    # that don't support equality checks
    disallowed_module_types = (ReportModule().module_type, CareplanModule().module_type)
    return [
        m for m in app.get_modules()
        if (m.id != module.id
            and m.module_type not in disallowed_module_types
            and m.case_type == module.case_type)
    ]


@register.filter
def get_available_modules_for_case_tile_configuration(app, module):
    valid_modules = get_available_modules_for_case_list_configuration(app, module)
    return [m for m in valid_modules if m.case_details.short.use_case_tiles]

