# get phone numbers of AWCs of specific states

import csv
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.dbaccessors import get_user_ids_by_location
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from django.db.models import Q
from corehq.apps.es.cases import CaseES
from corehq.elastic import ES_EXPORT_INSTANCE

domain = "icds-cas"
real_state_names = [
    loc.name 
    for loc in SQLLocation.active_objects.filter(domain=domain, location_type__code='state') 
    if loc.metadata.get('is_test_location') != 'test'
]

case_accessor = CaseAccessors(domain)
multiple_usercases_found_for_user_ids = []
no_usercases_found_for_user_ids = []

q = CaseES(es_instance_alias=ES_EXPORT_INSTANCE).domain(domain).term('type', USERCASE_TYPE)
with open('awc_phone_numbers_details.csv', 'w') as _file:
    writer = csv.DictWriter(_file, fieldnames=['case_type', 'case_id', 'location_id', 'name',
                                               'lang_code', 'contact_phone_number', 'verified', 'state'])
    writer.writeheader()
    for state_name in real_state_names:
         print(state_name)
         locations = list(SQLLocation.active_objects.get_descendants(Q(name=state_name)).filter(location_type__name='awc'
    ))
    print(len(locations))
    for location in locations:
        if location.metadata.get('is_test_location') != 'test':
            # Can consider using user_ids_at_locations to use ES instead of couch
            user_ids = get_user_ids_by_location(domain, location.location_id)
            if user_ids:
                for user_id in user_ids:
                    usercases = q.term('external_id', user_id).run().hits
                    if usercases:
                        if len(usercases) > 1:
                            multiple_usercases_found_for_user_ids.append(user_id)
                        for usercase in usercases:
                             writer.writerow({
                                 'case_type': usercase.get('type'),
                                 'case_id': usercase.get('case_id'),
                                 'location_id': location.location_id,
                                 'name': usercase.get('name'),
                                 'lang_code': usercase.get('language_code'),
                                 'contact_phone_number': usercase.get('contact_phone_number'),
                                 'verified': usercase.get('contact_phone_number_is_verified'),
                                 'state': state_name
                             })
                    else:
                        no_usercases_found_for_user_ids.append(user_id)

