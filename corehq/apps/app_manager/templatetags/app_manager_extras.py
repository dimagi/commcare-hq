from django import template


register = template.Library()


@register.filter
def get_available_modules_for_case_list_configuration(app, module):
    return [
        m for m in app.get_modules()
        if (m.id != module.id
            and m.module_type not in ('reports', 'careplan')
            and m.case_type == module.case_type)
    ]
