from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from couchforms.models import XFormInstance

def _get_place_mapping_to_fdi(domain, query_dict, place_types=None):
    place_types = place_types or []
    place_data_types = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()

    places_map = {} # will contain a mapping of place type to the fdi that corresponds with the specified name of the place
    for pt in place_types:
        places_map[pt] = query_dict.get(pt, None)
    for place_type, value in places_map.items():
        places_map[place_type] = FixtureDataItem.by_data_type_and_name(domain, place_data_types[place_type], value)

    return places_map, place_data_types

def _get_related_fixture_items(domain, data_types, fixture_items, fixture_name, fixture_id_name):
    # get the name of district
    for fdi in fixture_items:
        if not fdi:
            continue

        if fdi.data_type_id == data_types.get(fixture_name, None).get_id:
            return fdi.fields['name']

        d_id = fdi.fields.get(fixture_id_name, None)
        if d_id:
            district_item = FixtureDataItem.by_data_type_and_name(domain, data_types[fixture_name], d_id)
            return district_item.fields['name']
    return None

def psi_events(domain, query_dict):
    place_types = ['block', 'state', 'district']
    places, pdts = _get_place_mapping_to_fdi(domain, query_dict, place_types=place_types)
    resp_dict = {}

    # get the name of district
    name_of_district = _get_related_fixture_items(domain, pdts, places.values(), 'district', 'district_id')
    if name_of_district:
        resp_dict["name_of_district"] = name_of_district

    def ff_func(form):
        loc = query_dict.get('location', None)
        if loc:
            if not form.xpath('form/event_location') == loc:
                return False
        return form.form.get('@name', None) == 'Plays and Events'

    forms = list(_get_forms(domain, form_filter=ff_func))
    resp_dict.update({
        "num_male": reduce(lambda sum, f: sum + f.xpath('form/number_of_males'), forms, 0),
        "num_female": reduce(lambda sum, f: sum + f.xpath('form/number_of_females'), forms, 0),
        "num_total": reduce(lambda sum, f: sum + f.xpath('form/number_of_attendees'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + f.xpath('form/number_of_leaflets'), forms, 0),
        "num_gifts": reduce(lambda sum, f: sum + f.xpath('form/number_of_gifts'), forms, 0)
    })
    return resp_dict

def psi_household_demonstrations(domain, query_dict):
    place_types = ['block', 'state', 'district', 'village']
    places, pdts = _get_place_mapping_to_fdi(domain, query_dict, place_types=place_types)
    resp_dict = {}

    name_of_district = _get_related_fixture_items(domain, pdts, places.values(), 'district', 'district_id')
    if name_of_district:
        resp_dict["name_of_district"] = name_of_district
    name_of_block = _get_related_fixture_items(domain, pdts, places.values(), 'block', 'block_id')
    if name_of_block:
        resp_dict["name_of_block"] = name_of_block
    name_of_village = _get_related_fixture_items(domain, pdts, places.values(), 'village', 'village_id')
    if name_of_village:
        resp_dict["name_of_village"] = name_of_village

    def ff_func(form):
        wt = query_dict.get('worker_type', None)
        if wt:
            if not form.xpath('form/demo_type') == wt:
                return False
        return form.form.get('@name', None) == 'Household Demonstration'

    forms = list(_get_forms(domain, form_filter=ff_func))
    resp_dict.update({
        "num_hh_demo": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'hh_covered'), forms, 0),
        "num_young": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'number_young_children_covered'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'leaflets_distributed'), forms, 0),
        "num_kits": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'kits_sold'), forms, 0),
        })
    return resp_dict

def psi_sensitization_sessions(domain, query_dict):
    place_types = ['block', 'state', 'district']
    places, pdts = _get_place_mapping_to_fdi(domain, query_dict, place_types=place_types)
    resp_dict = {}

    name_of_district = _get_related_fixture_items(domain, pdts, places.values(), 'district', 'district_id')
    if name_of_district:
        resp_dict["name_of_district"] = name_of_district
    name_of_block = _get_related_fixture_items(domain, pdts, places.values(), 'block', 'block_id')
    if name_of_block:
        resp_dict["name_of_block"] = name_of_block
    name_of_state = _get_related_fixture_items(domain, pdts, places.values(), 'state', 'state_id')
    if name_of_state:
        resp_dict["name_of_state"] = name_of_state

    def ff_func(form):
        return form.form.get('@name', None) == 'Sensitization Session'

    forms = list(_get_forms(domain, form_filter=ff_func))

    def rf_func(data):
        return data.get('type_of_sensitization', None) == 'vhnd'

    resp_dict.update({
        "num_sessions": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'number_of_blm_attended'), forms, 0) +
                        reduce(lambda sum, f: sum + len(list(_get_repeats(f.xpath('form/training_sessions'), repeat_filter=rf_func))), forms, 0),
        "num_ayush_doctors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_ayush_doctors'), forms, 0),
        "num_mbbs_doctors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_mbbs_doctors'), forms, 0),
        "num_asha_supervisors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_asha_supervisors'), forms, 0),
        "num_ashas": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_ashas'), forms, 0),
        "num_awws": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_awws'), forms, 0),
        "num_other": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_other'), forms, 0),
        "number_attendees": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'number_attendees'), forms, 0),
        })
    return resp_dict

def psi_training_sessions(domain, query_dict):
    place_types = ['state', 'district']
    places, pdts = _get_place_mapping_to_fdi(domain, query_dict, place_types=place_types)
    resp_dict = {}

    name_of_district = _get_related_fixture_items(domain, pdts, places.values(), 'district', 'district_id')
    if name_of_district:
        resp_dict["name_of_district"] = name_of_district
    name_of_state = _get_related_fixture_items(domain, pdts, places.values(), 'state', 'state_id')
    if name_of_state:
        resp_dict["name_of_state"] = name_of_state

    def ff_func(form):
        tt = query_dict.get('training_type', None)
        if tt:
            if not form.xpath('form/training_type') == tt:
                return False
        return form.form.get('@name', None) == 'Training Session'

    forms = list(_get_forms(domain, form_filter=ff_func))
    private_forms = filter(lambda f: f.xpath('form/trainee_category') == 'private', forms)
    public_forms = filter(lambda f: f.xpath('form/trainee_category') == 'public', forms)
    dh_forms = filter(lambda f: f.xpath('form/trainee_category') == 'depot_holder', forms)
    flw_forms = filter(lambda f: f.xpath('form/trainee_category') == 'flw_training', forms)

    resp_dict.update({
        "private_hcp": _indicators(private_forms, aa=True),
        "public_hcp": _indicators(public_forms, aa=True),
        "depot_training": _indicators(dh_forms),
        "flw_training": _indicators(flw_forms),
        })
    return resp_dict

def _indicators(forms, aa=False):
    ret = { "num_forms": len(forms),
            "num_trained": _num_trained(forms)}
    if aa:
        ret.update({
            "num_ayush_trained": _num_trained(forms, doctor_type="ayush"),
            "num_allopathics_trained": _num_trained(forms, doctor_type="allopathic"),
            })
    ret.update(_scores(forms))
    return ret

def _num_trained(forms, doctor_type=None):
    def rf_func(data):
        return data.get('doctor_type', None) == doctor_type if doctor_type else True
    return reduce(lambda sum, f: sum + len(list(_get_repeats(f.xpath('form/trainee_information'), repeat_filter=rf_func))), forms, 0)

def _scores(forms):
    trainees = []

    for f in forms:
        trainees.extend(list(_get_repeats(f.xpath('form/trainee_information'))))

    total_pre_scores = reduce(lambda sum, t: sum + int(t.get("pre_test_score", 0)), trainees, 0)
    total_post_scores = reduce(lambda sum, t: sum + int(t.get("post_test_score", 0)), trainees, 0)
    total_diffs = reduce(lambda sum, t: sum + (int(t.get("post_test_score", 0)) - int(t.get("pre_test_score", 0))), trainees, 0)

    return {
        "avg_pre_score": total_pre_scores/len(trainees) if trainees else "No Data",
        "avg_post_score": total_post_scores/len(trainees) if trainees else "No Data",
        "avg_difference": total_diffs/len(trainees) if trainees else "No Data",
        "num_gt80": len(filter(lambda t: t.get("post_test_score", 0) >= 80.0, trainees))/len(trainees) if trainees else "No Data"
    }

def _get_repeats(data, repeat_filter=lambda r: True):
    if not isinstance(data, list):
        data = [data]
    for d in data:
        if repeat_filter(d):
            yield d

def _count_in_repeats(data, what_to_count):
    if not isinstance(data, list):
        data = [data]
    return reduce(lambda sum, d: sum + int(d.get(what_to_count, 0) or 0), data, 0)

def _get_all_form_submissions(domain):
    submissions = XFormInstance.view('reports/all_submissions',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False
    )
    return submissions


def _get_forms(domain, form_filter=lambda f: True):
    for form in _get_all_form_submissions(domain):
        if form_filter(form):
            yield form

def _get_form(domain, action_filter=lambda a: True, form_filter=lambda f: True):
    """
    returns the first form that passes through the form filter function
    """
    gf = _get_forms(domain, form_filter=form_filter)
    try:
        return gf.next()
    except StopIteration:
        return None