from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance

def _get_unique_combinations(domain, place_types=None):
    if not place_types:
        return []
    place_data_types = {}
    place_data_items = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()
        place_data_items[pt] = FixtureDataItem.by_data_type(domain, place_data_types[pt])

    fdis = []; base_type = ""
    for t in ["village", "block", "district", "state"]:
        if t in place_types:
            base_type = t
            fdis = FixtureDataItem.by_data_type(domain, place_data_types[t].get_id)
            break

    combos = []
    for fdi in fdis:
        comb = {}
        for pt in place_types:
            if base_type == pt:
                comb[pt] = fdi.fields['name']
            else:
                p_id = fdi.fields.get(pt+"_id", None)
                if p_id:
                    comb[pt] = p_id
#                    for item in place_data_items[pt]:
#                        if item.fields["id"] == p_id:
#                            comb[pt] = item.fields['name']
                else:
                    comb[pt] = None
        combos.append(comb)

    return combos

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
    place_types = ['state', 'district']
#    import pprint
#    pp = pprint.PrettyPrinter(indent=2)
#    pp.pprint(_get_unique_combinations(domain, place_types=place_types))
#    places, pdts = _get_place_mapping_to_fdi(domain, query_dict, place_types=place_types)
    combos = _get_unique_combinations(domain, place_types=place_types)
#    import pprint
#    pp = pprint.PrettyPrinter(indent=2)
#    pp.pprint(combos)
    forms = list(_get_forms(domain))
    print "forms: %s" % [f.get_id for f in forms]
    return map(lambda c: event_stats(domain, c, query_dict.get("location", "")), combos)

def event_stats(domain, place_dict, location=""):
    def ff_func(form):
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if location:
            if not form.xpath('form/event_location') == location:
                return False
        return form.form.get('@name', None) == 'Plays and Events'

    forms = list(_get_forms(domain, form_filter=ff_func))
#    if forms:
#        print "HERE LIE SOME FORMS"
#    else:
#        print "sigh"
    place_dict.update({
        "location": location,
        "num_male": reduce(lambda sum, f: sum + f.xpath('form/number_of_males'), forms, 0),
        "num_female": reduce(lambda sum, f: sum + f.xpath('form/number_of_females'), forms, 0),
        "num_total": reduce(lambda sum, f: sum + f.xpath('form/number_of_attendees'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + f.xpath('form/number_of_leaflets'), forms, 0),
        "num_gifts": reduce(lambda sum, f: sum + f.xpath('form/number_of_gifts'), forms, 0)
    })
    return place_dict

def psi_household_demonstrations(domain, query_dict):
    place_types = ['block', 'state', 'district', 'village']
    combos = _get_unique_combinations(domain, place_types=place_types)
    print "length: %s" % len(combos)
    return map(lambda c: hd_stats(domain, c, query_dict.get("worker_type", "")), combos)

def hd_stats(domain, place_dict, worker_type=""):
    def ff_func(form):
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if place_dict["block"] and form.xpath('form/activity_block') != place_dict["block"]:
            return False
        if place_dict["village"] and form.xpath('form/activity_village') != place_dict["village"]:
            return False
        if worker_type:
            if not form.xpath('form/demo_type') == worker_type:
                return False
        return form.form.get('@name', None) == 'Household Demonstration'

    forms = list(_get_forms(domain, form_filter=ff_func))
    place_dict.update({
        "num_hh_demo": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'hh_covered'), forms, 0),
        "num_young": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'number_young_children_covered'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'leaflets_distributed'), forms, 0),
        "num_kits": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'kits_sold'), forms, 0),
        })
    return place_dict

def psi_sensitization_sessions(domain, query_dict):
    place_types = ['state', 'district', 'block']
    combos = _get_unique_combinations(domain, place_types=place_types)
    print "length: %s" % len(combos)
    return map(lambda c: ss_stats(domain, c), combos)

def ss_stats(domain, place_dict):
    def ff_func(form):
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if place_dict["block"] and form.xpath('form/activity_block') != place_dict["block"]:
            return False
        return form.form.get('@name', None) == 'Sensitization Session'

    forms = list(_get_forms(domain, form_filter=ff_func))

    def rf_func(data):
        return data.get('type_of_sensitization', None) == 'vhnd'

    place_dict.update({
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
    return place_dict


def psi_training_sessions(domain, query_dict):
    place_types = ['state', 'district']
    combos = _get_unique_combinations(domain, place_types=place_types)
    print "length: %s" % len(combos)
    return map(lambda c: ts_stats(domain, c, query_dict.get("training_type", "")), combos)

def ts_stats(domain, place_dict, training_type=""):
    def ff_func(form):
        if place_dict["state"] and form.xpath('form/training_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/training_district') != place_dict["district"]:
            return False
        if training_type:
            if not form.xpath('form/training_type') == training_type:
                return False
        return form.form.get('@name', None) == 'Training Session'

    forms = list(_get_forms(domain, form_filter=ff_func))
    private_forms = filter(lambda f: f.xpath('form/trainee_category') == 'private', forms)
    public_forms = filter(lambda f: f.xpath('form/trainee_category') == 'public', forms)
    dh_forms = filter(lambda f: f.xpath('form/trainee_category') == 'depot_holder', forms)
    flw_forms = filter(lambda f: f.xpath('form/trainee_category') == 'flw_training', forms)

    place_dict.update({
        "private_hcp": _indicators(private_forms, aa=True),
        "public_hcp": _indicators(public_forms, aa=True),
        "depot_training": _indicators(dh_forms),
        "flw_training": _indicators(flw_forms),
        })
    return place_dict

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
    key = make_form_couch_key(domain)
    submissions = XFormInstance.view('reports_forms/all_forms',
        startkey=key,
        endkey=key+[{}],
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

class PSIEventsReport(GenericTabularReport):
    name = "DCC Activity Report"
    slug = "hsph_dcc_activity"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCCField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Location"),
            DataTablesColumn("Number of male attendees"),
            DataTablesColumn("Number of female attendees"),
            DataTablesColumn("Total number of attendees"),
            DataTablesColumn("Total number of leaflets distributed"),
            DataTablesColumn("Total number of gifts distributed"))

    @property
    def rows(self):
        rows = []
