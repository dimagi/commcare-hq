from corehq.apps.data_dictionary.models import CaseType, CaseProperty


def setup_data_dictionary(domain, case_type_name, prop_list=None):
    prop_list = prop_list or []
    CaseType.get_or_create(domain, case_type_name)
    for prop_name, data_type in prop_list:
        prop = CaseProperty.get_or_create(prop_name, case_type_name, domain)
        prop.data_type = data_type
        prop.save()
