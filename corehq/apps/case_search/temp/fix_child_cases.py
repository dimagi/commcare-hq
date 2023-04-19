from corehq.form_processor.models import CommCareCase
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.locations.models import SQLLocation

DOMAIN = ''
CHILD_CASE_TYPE = 'membre'

case_ids = CommCareCase.objects.get_case_ids_in_domain(domain=DOMAIN, type=CHILD_CASE_TYPE)

total_cases = len(case_ids)
cases_checked = 0

for child_case in CommCareCase.objects.iter_cases(case_ids, domain=DOMAIN):
    parent_case = child_case.parent
    parent_missing = parent_case is None
    owner_ids_match = parent_case and parent_case.owner_id == child_case.owner_id
    
    if parent_missing or owner_ids_match:
        continue
    """
        Step 1 - Update child case's owner_id to that of its parent case
    """
    child_case_helper = CaseHelper(domain=DOMAIN, case=child_case)
    child_case_helper.update({'owner_id': parent_case.owner_id})
    
    """
        Step 2 - Make sure that the case properties of both the child and parent cases correspond to te
        village's hierarchy. The owner_id of both cases is the village id
    """
    village_id = parent_case.owner_id

    village = SQLLocation.objects.get(location_id=village_id, domain=DOMAIN)
    formation_sanitaire = village.parent
    arrondissement = formation_sanitaire.parent
    commune = arrondissement.parent
    zone_sanitaire = commune.parent
    departement = zone_sanitaire.parent

    correct_properties = {
        "hh_village_name": village.name,
        "hh_formation_sanitaire_name": formation_sanitaire.parent.name,
        "hh_arrondissement_name": arrondissement.name,
        "hh_commune_name": commune.name,
        "hh_zone_sanitaire_name": zone_sanitaire.name,
        "hh_departement_name": departement.name
    }

    parent_case_helper = CaseHelper(domain=DOMAIN, case=parent_case)
    case_helpers = [parent_case_helper, child_case_helper]
    cases = [parent_case, child_case]

    for case, case_helper in zip(cases, case_helpers):
        updated_properties = {}
        for property_name, correct_property_value in correct_properties:
            curr_case_property_value = case.get_case_property(property_name)

            if (not curr_case_property_value) or (curr_case_property_value != correct_property_value):
                updated_properties[property_name] = correct_property_value
        
        case_helper.update({'properties': updated_properties})
                

    # Statistics
    cases_checked += 1
    progress = round(cases_checked/total_cases, 3)
    print(f"{progress}% complete")
