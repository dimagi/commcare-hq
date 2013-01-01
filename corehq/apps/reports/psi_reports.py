from django.utils.translation import ugettext_noop
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.reports.fields import ReportField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance
from corehq.apps.reports.cache import CacheableRequestMixIn, request_cache
import json

def _get_unique_combinations(domain, place_types=None, place_id=None):
    if not place_types:
        return []
    if place_id:
        place_type_from_id = place_id.split(':')[0]
        place_name = place_id.split(':')[1].lower()

    place_data_types = {}
#    place_data_items = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()
#        place_data_items[pt] = FixtureDataItem.by_data_type(domain, place_data_types[pt])

    fdis = []; base_type = ""
    for t in ["village", "block", "district", "state"]:
        if t in place_types:
            base_type = t
            fdis = FixtureDataItem.by_data_type(domain, place_data_types[t].get_id)
            break

    combos = []
    for fdi in fdis:
        if place_id:
            if base_type == place_type_from_id:
                if fdi.fields['name'].lower() != place_name:
                    continue
            else:
                if fdi.fields.get(place_type_from_id+"_id", "").lower() != place_name:
                    continue
        comb = {}
        for pt in place_types:
            if base_type == pt:
                comb[pt] = fdi.fields['name'].lower()
            else:
                p_id = fdi.fields.get(pt+"_id", None)
                if p_id:
                    if place_id and pt == place_type_from_id and p_id != place_name:
                        continue
                    comb[pt] = p_id
#                    for item in place_data_items[pt]:
#                        if item.fields["id"] == p_id:
#                            comb[pt] = item.fields['name']
                else:
                    comb[pt] = None
        combos.append(comb)

    return combos

def psi_events(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: event_stats(domain, c, query_dict.get("location", "")), combos)

def event_stats(domain, place_dict, location="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Plays and Events':
            return False
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if location:
            if not form.xpath('form/event_location') == location:
                return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func))
    place_dict.update({
        "location": location,
        "num_male": reduce(lambda sum, f: sum + f.xpath('form/number_of_males'), forms, 0),
        "num_female": reduce(lambda sum, f: sum + f.xpath('form/number_of_females'), forms, 0),
        "num_total": reduce(lambda sum, f: sum + f.xpath('form/number_of_attendees'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + f.xpath('form/number_of_leaflets'), forms, 0),
        "num_gifts": reduce(lambda sum, f: sum + f.xpath('form/number_of_gifts'), forms, 0)
    })
    return place_dict

def psi_household_demonstrations(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['block', 'state', 'district', 'village']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: hd_stats(domain, c, query_dict.get("worker_type", "")), combos)

def hd_stats(domain, place_dict, worker_type="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Household Demonstration':
            return False
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
        return True

    forms = list(_get_forms(domain, form_filter=ff_func))
    place_dict.update({
        "worker_type": worker_type,
        "num_hh_demo": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'hh_covered'), forms, 0),
        "num_young": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'number_young_children_covered'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'leaflets_distributed'), forms, 0),
        "num_kits": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'kits_sold'), forms, 0),
        })
    return place_dict

def psi_sensitization_sessions(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district', 'block']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: ss_stats(domain, c), combos)

def ss_stats(domain, place_dict, startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Sensitization Session':
            return False
        if place_dict["state"] and form.xpath('form/training_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/training_district') != place_dict["district"]:
            return False
        if place_dict["block"] and form.xpath('form/training_block') != place_dict["block"]:
            return False
        return True

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


def psi_training_sessions(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: ts_stats(domain, c, query_dict.get("training_type", "")), combos)

def ts_stats(domain, place_dict, training_type="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Training Session':
            return False
        if place_dict["state"] and form.xpath('form/training_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/training_district') != place_dict["district"]:
            return False
        if training_type:
            if not form.xpath('form/training_type') == training_type:
                return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func))

    all_forms = list(_get_forms(domain, form_filter=lambda f: f.form.get('@name', None) == 'Training Session'))
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
    return reduce(lambda sum, f: sum + len(list(_get_repeats(f.xpath('form/trainee_information'), repeat_filter=rf_func))), forms, 0)

def _scores(forms):
    trainees = []

    for f in forms:
        trainees.extend(list(_get_repeats(f.xpath('form/trainee_information'))))

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

def within_time_period(form, startdate, enddate):
    return True

class PSIReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.DatespanField','corehq.apps.reports.psi_reports.PlaceField',]

class PSIEventsReport(PSIReport):
    name = "Event Demonstration Report"
    slug = "event_demonstations"
    section_name = "event demonstrations"

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
        event_data = psi_events(self.domain, {}, place_id=self.request.GET.get('location_id', ""))
        for d in event_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("location"),
                d.get("num_male"),
                d.get("num_female") ,
                d.get("num_total"),
                d.get("num_leaflets"),
                d.get("num_gifts")
            ]

class PSIHDReport(PSIReport):
    name = "Household Demonstrations Report"
    slug = "household_demonstations"
    section_name = "household demonstrations"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Name of Block"),
            DataTablesColumn("Name of Town/Village"),
            DataTablesColumn("Number of HH demos done"),
            DataTablesColumn("Demonstration done by"),
            DataTablesColumn("Number of 0-6 year old children"),
            DataTablesColumn("Number of leaflets distributed"),
            DataTablesColumn("Number of kits sold"))

    @property
    def rows(self):
        hh_data = psi_household_demonstrations(self.domain, {}, place_id=self.request.GET.get('location_id', ""))
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("block"),
                d.get("village"),
                d.get("num_hh_demo") ,
                d.get("worker_type"),
                d.get("num_young"),
                d.get("num_leaflets"),
                d.get("num_kits"),
            ]

class PSISSReport(PSIReport):
    name = "Sensitization Sessions Report"
    slug = "sensitization_sessions"
    section_name = "sensitization sessions"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Name of Block"),
            DataTablesColumn("Number of Sessions"),
            DataTablesColumn("Ayush Trained"),
            DataTablesColumn("MBBS Trained"),
            DataTablesColumn("Asha Supervisors Trained"),
            DataTablesColumn("Ashas Trained"),
            DataTablesColumn("AWW Trained"),
            DataTablesColumn("Other Trained"),
            DataTablesColumn("VHND Attendees"))

    @property
    def rows(self):
        hh_data = psi_sensitization_sessions(self.domain, {}, place_id=self.request.GET.get('location_id', ""))
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("block"),
                d.get("num_sessions") ,
                d.get("num_ayush_doctors"),
                d.get("num_mbbs_doctors"),
                d.get("num_asha_supervisors"),
                d.get("num_ashas"),
                d.get("num_awws"),
                d.get("num_other"),
                d.get("number_attendees"),
            ]

class PSITSReport(PSIReport):
    name = "Training Sessions Report"
    slug = "training_sessions"
    section_name = "training sessions"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Type of Training"),
            DataTablesColumn("Private: Number of Trainings"),
            DataTablesColumn("Private: Ayush trained"),
            DataTablesColumn("Private: Allopathics trained"),
            DataTablesColumn("Private: Learning change"),
            DataTablesColumn("Private: Num > 80%"),
            DataTablesColumn("Public: Number of Trainings"),
            DataTablesColumn("Public: Ayush trained"),
            DataTablesColumn("Public: Allopathics trained"),
            DataTablesColumn("Public: Learning change"),
            DataTablesColumn("Public: Num > 80%"),
            DataTablesColumn("Depot: Number of Trainings"),
#            DataTablesColumn("Depot: Personnel trained"),
            DataTablesColumn("Depot: Learning change"),
            DataTablesColumn("Depot: Num > 80%"),
            DataTablesColumn("FLW: Number of Trainings"),
#            DataTablesColumn("FLW: Personnel trained"),
            DataTablesColumn("FLW: Learning change"),
            DataTablesColumn("FLW: Num > 80%"))

    @property
    def rows(self):
#        print self.datespan.startdate_param_utc
#        print self.datespan.enddate_param_utc
        hh_data = psi_training_sessions(self.domain, {}, place_id=self.request.GET.get('location_id', ""))
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("training_type"),
                d["private_hcp"].get("num_trained"),
                d["private_hcp"].get("num_ayush_trained"),
                d["private_hcp"].get("num_allopathics_trained"),
                d["private_hcp"].get("avg_difference"),
                d["private_hcp"].get("num_gt80"),
                d["public_hcp"].get("num_trained"),
                d["public_hcp"].get("num_ayush_trained"),
                d["public_hcp"].get("num_allopathics_trained"),
                d["public_hcp"].get("avg_difference"),
                d["public_hcp"].get("num_gt80"),
                d["depot_training"].get("num_trained"),
                d["depot_training"].get("avg_difference"),
                d["depot_training"].get("num_gt80"),
                d["flw_training"].get("num_trained"),
                d["flw_training"].get("avg_difference"),
                d["flw_training"].get("num_gt80"),
            ]

def place_tree(domain):
    fdis = []; base_type = ""
    place_data_types = {}
    place_data_items = {}
    for pt in ["village", "block", "district", "state"]:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()
        place_data_items[pt] = FixtureDataItem.by_data_type(domain, place_data_types[pt].get_id).all()

    pdis_by_id = {}
    for pt, items in place_data_items.iteritems():
        pdis_by_id.update(dict((pdi.fields['id'], pdi) for pdi in items))

    tree_root = []
    for item in place_data_items["state"]:
        item._children = []
        item._place = "state"
        tree_root.append(item)

    for item in place_data_items["district"]:
        item._children = []
        item._place = "district"
        if item.fields.get('state_id', None):
            parent = pdis_by_id[item.fields['state_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                print "Error: %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    for item in place_data_items["block"]:
        item._children = []
        item._place = "block"
        if item.fields.get('district_id', None):
            parent = pdis_by_id[item.fields['district_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                print "Error: %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    for item in place_data_items["village"]:
        item._children = []
        item._place = "village"
        if item.fields.get('block_id', None):
            parent = pdis_by_id[item.fields['block_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                print "Error: %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    return tree_root

class PlaceField(ReportField):
    name = ugettext_noop("State/District/Block/Village")
    slug = "place"
    template = "reports/fields/location.html"
    is_cacheable = True

    def update_context(self):
        self.context.update(self._get_custom_context())

    @request_cache('placefieldcontext')
    def _get_custom_context(self):
        all_locs = place_tree(self.domain)
        def loc_to_json(loc):
            return {
                'name': loc.fields['name'],
#                'type': loc.location_type,
                'uuid': "%s:%s" % (loc._place, loc.fields['name']),
                'children': [loc_to_json(child) for child in loc._children],
                }
        loc_json = [loc_to_json(root) for root in all_locs]

        return {
            'control_name': self.name,
            'control_slug': self.slug,
            'loc_id': self.request.GET.get('location_id'),
            'locations': json.dumps(loc_json)
        }

