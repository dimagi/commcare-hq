from corehq.apps.geospatial.models import GeoConfig

from dimagi.utils.couch.bulk import get_docs
from casexml.apps.case.mock import CaseBlock

from corehq.form_processor.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.hqcase.utils import submit_case_blocks


def get_geo_case_property(domain):
    try:
        config = GeoConfig.objects.get(domain=domain)
    except GeoConfig.DoesNotExist:
        config = GeoConfig()
    return config.case_location_property_name


def get_geo_user_property(domain):
    try:
        config = GeoConfig.objects.get(domain=domain)
    except GeoConfig.DoesNotExist:
        config = GeoConfig()
    return config.user_location_property_name


def _get_mapping(data_items):
    return {
        i['id']: f"{i['lat']} {i['lon']}"
        for i in data_items
        if i['lat'] and i['lon']
    }


def process_gps_values_for_cases(domain, cases):
    location_prop_name = get_geo_case_property(domain)
    case_mapping = _get_mapping(cases)
    case_list = CommCareCase.objects.get_cases(list(case_mapping.keys()), domain=domain)
    case_blocks = []
    for c in case_list:
        props = c.case_json
        props[location_prop_name] = case_mapping[c.case_id]
        case_block = CaseBlock(
            create=False,
            case_id=c.case_id,
            owner_id=c.owner_id,
            case_type=c.type,
            case_name=c.name,
            update=props,
            index=c.get_index_map(),
        )
        case_blocks.append(case_block.as_text())
    return submit_case_blocks(
        case_blocks=case_blocks,
        domain=domain,
    )


def process_gps_values_for_users(domain, users):
    location_prop_name = get_geo_user_property(domain)
    user_mapping = _get_mapping(users)
    user_docs_to_save = []
    for user_doc in get_docs(CommCareUser.get_db(), keys=list(user_mapping.keys())):
        user_id = user_doc['_id']
        user_doc['user_data'][location_prop_name] = user_mapping[user_id]
        user_docs_to_save.append(user_doc)

    if user_docs_to_save:
        CommCareUser.get_db().bulk_save(user_docs_to_save)

    for user_doc in user_docs_to_save:
        commcare_user = CommCareUser.wrap(user_doc)
        commcare_user.clear_quickcache_for_user()
        commcare_user.fire_signals()
