from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance


def get_unique_combinations(domain, place_types=None, place=None):
    if not place_types:
        return []
    if place:
        place_type = place[0]
        place = FixtureDataItem.get(place[1])
        place_name = place.fields['id']

    place_data_types = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()

    relevant_types =  [t for t in ["village", "block", "district", "state"] if t in place_types]
    base_type = relevant_types[0] if relevant_types else ""
    fdis = FixtureDataItem.by_data_type(domain, place_data_types[base_type].get_id) if base_type else []

    combos = []
    for fdi in fdis:
        if place:
            if base_type == place_type:
                if fdi.fields['id'] != place_name:
                    continue
            else:
                if fdi.fields.get(place_type+"_id", "").lower() != place_name:
                    continue
        comb = {}
        for pt in place_types:
            if base_type == pt:
                comb[pt] = str(fdi.fields['id'])
            else:
                p_id = fdi.fields.get(pt+"_id", None)
                if p_id:
                    if place and pt == place_type and p_id != place_name:
                        continue
                    comb[pt] = str(p_id)
                else:
                    comb[pt] = None
        combos.append(comb)
    return combos

def psi_training_sessions(domain, query_dict, startdate=None, enddate=None, place=None):
    place_types = ['state', 'district']
    combos = get_unique_combinations(domain, place_types=place_types, place=place)
    return map(lambda c: ts_stats(domain, c, query_dict.get("training_type", ""), startdate=startdate, enddate=enddate), combos)

def ts_stats(domain, place_dict, training_type="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Training Session':
            return False
        if place_dict["state"] and str(form.xpath('form/training_state')) != place_dict["state"]:
            return False
        if place_dict["district"] and str(form.xpath('form/training_district')) != place_dict["district"]:
            return False
        if training_type:
            if not form.xpath('form/training_type') == training_type:
                return False
        return True

    forms = list(get_forms(domain, form_filter=ff_func, startdate=startdate, enddate=enddate))

    all_forms = list(get_forms(domain, form_filter=lambda f: f.form.get('@name', None) == 'Training Session'))
    private_forms = filter(lambda f: f.xpath('form/trainee_category') == 'private', forms)
    public_forms = filter(lambda f: f.xpath('form/trainee_category') == 'public', forms)
    dh_forms = filter(lambda f: f.xpath('form/trainee_category') == 'depot_holder', forms)
    flw_forms = filter(lambda f: f.xpath('form/trainee_category') == 'flw_training', forms)

    place_dict.update({
        "training_type": training_type,
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
        if data:
            return data.get('doctor_type', None) == doctor_type if doctor_type else True
        else:
            return False
    return reduce(lambda sum, f: sum + len(list(get_repeats(f.xpath('form/trainee_information'), repeat_filter=rf_func))), forms, 0)

def _scores(forms):
    trainees = []

    for f in forms:
        trainees.extend(list(get_repeats(f.xpath('form/trainee_information'))))

    trainees = filter(lambda t: t, trainees)
    total_pre_scores = reduce(lambda sum, t: sum + int(t.get("pre_test_score", 0) or 0), trainees, 0)
    total_post_scores = reduce(lambda sum, t: sum + int(t.get("post_test_score", 0) or 0), trainees, 0)
    total_diffs = reduce(lambda sum, t: sum + (int(t.get("post_test_score", 0) or 0) - int(t.get("pre_test_score", 0) or 0)), trainees, 0)

    return {
        "avg_pre_score": total_pre_scores/len(trainees) if trainees else "No Data",
        "avg_post_score": total_post_scores/len(trainees) if trainees else "No Data",
        "avg_difference": total_diffs/len(trainees) if trainees else "No Data",
        "num_gt80": len(filter(lambda t: t.get("post_test_score", 0) or 0 >= 80.0, trainees))/len(trainees) if trainees else "No Data"
    }

def get_repeats(data, repeat_filter=lambda r: True):
    if not isinstance(data, list):
        data = [data]
    for d in data:
        if repeat_filter(d):
            yield d

def count_in_repeats(data, what_to_count):
    if not isinstance(data, list):
        data = [data]
    return reduce(lambda sum, d: sum + int(d.get(what_to_count, 0) or 0), data, 0)

def _get_all_form_submissions(domain, startdate=None, enddate=None):
    key = make_form_couch_key(domain)
    startkey = key+[startdate] if startdate and enddate else key
    endkey = key+[enddate] if startdate and enddate else key + [{}]
    submissions = XFormInstance.view('reports_forms/all_forms',
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
        reduce=False
    )
    return submissions


def get_forms(domain, form_filter=lambda f: True, startdate=None, enddate=None):
    for form in _get_all_form_submissions(domain, startdate=startdate, enddate=enddate):
        if form_filter(form):
            yield form

def get_form(domain, action_filter=lambda a: True, form_filter=lambda f: True):
    """
    returns the first form that passes through the form filter function
    """
    gf = get_forms(domain, form_filter=form_filter)
    try:
        return gf.next()
    except StopIteration:
        return None