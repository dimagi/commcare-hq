from corehq.apps.data_dictionary.models import CaseType, CaseProperty, CasePropertyAllowedValue


def setup_data_dictionary(domain, case_type_name, prop_list=None, allowed_values=None, required=None):
    prop_list = prop_list or []
    allowed_values = allowed_values or {}
    CaseType.get_or_create(domain, case_type_name)
    for prop_name, data_type in prop_list:
        prop = CaseProperty.get_or_create(prop_name, case_type_name, domain)
        prop.data_type = data_type
        if required and prop_name in required:
            prop.required = True
        prop.save()
        if prop_name in allowed_values:
            for value in allowed_values[prop_name]:
                CasePropertyAllowedValue.objects.get_or_create(case_property=prop, allowed_value=value)
