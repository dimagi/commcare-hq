from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.basic import BasicTabularReport, Column
from corehq.apps.reports.fields import AsyncDrillableField
from util import get_unique_combinations
from couchdbkit_aggregate.fn import mean
from dimagi.utils.decorators.memoized import memoized

class StateDistrictField(AsyncDrillableField):
    label = "State and District"
    slug = "location"
    hierarchy = [{"type": "state", "display": "name"},
                 {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},]

class StateDistrictBlockField(AsyncDrillableField):
    label = "State/District/Block"
    slug = "location"
    hierarchy = [{"type": "state", "display": "name"},
                 {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
                 {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"}]

class AsyncPlaceField(AsyncDrillableField):
    label = "State/District/Block/Village"
    slug = "location"
    hierarchy = [{"type": "state", "display": "name"},
                 {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
                 {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"},
                 {"type": "village", "parent_ref": "block_id", "references": "id", "display": "name"}]

class PSIReport(BasicTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.DatespanField','psi.reports.AsyncPlaceField',]

    def selected_fixture(self):
        fixture = self.request.GET.get('fixture_id', "")
        return fixture.split(':') if fixture else None

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

class PSIEventsReport(PSIReport):
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',]
    name = "Event Demonstration Report"
    exportable = True
    slug = "event_demonstations"
    section_name = "event demonstrations"

    couch_view = 'psi/events'

    default_column_order = (
        'state_name',
        'district_name',
        'males',
        'females',
        'attendees',
        'leaflets',
        'gifts',
        )

    state_name = Column("State", calculate_fn=lambda key, _: key[0])

    district_name = Column("District", calculate_fn=lambda key, _: key[1])

    males = Column("Number of male attendees", key='males')

    females = Column("Number of female attendees", key='females')

    attendees = Column("Total number of attendees", key='attendees')

    leaflets = Column("Total number of leaflets distributed", key='leaflets')

    gifts = Column("Total number of gifts distributed", key='gifts')

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=['state', 'district'], place=self.selected_fixture())

        for c in combos:
            yield [c['state'], c['district']]

@memoized
def get_village_fdt(domain):
    return FixtureDataType.by_domain_tag(domain, 'village').one()

def get_village_name(key, req):
    village_fdt = get_village_fdt(req.domain)
    id = key[3]
    village_fdi = FixtureDataItem.by_field_value(req.domain, village_fdt, 'id', float(id)).one()
    return "%s (%s)" % (village_fdi.fields.get("name", id), id) if village_fdi else id

class PSIHDReport(PSIReport):
    name = "Household Demonstrations Report"
    exportable = True
    slug = "household_demonstations"
    section_name = "household demonstrations"

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain,
            place_types=['state', 'district', "block", "village"], place=self.selected_fixture())

        for c in combos:
            yield [c['state'], c['district'], c["block"], c["village"]]

    couch_view = 'psi/household_demonstrations'

    default_column_order = (
        'state_name',
        'district_name',
        "block_name",
        "village_name",
        'demonstrations',
        #        'worker_type',
        'children',
        'leaflets',
        'kits',
        )

    state_name = Column("State", calculate_fn=lambda key, _: key[0])

    district_name = Column("District", calculate_fn=lambda key, _: key[1])

    block_name = Column("Block", calculate_fn=lambda key, _: key[2])

    village_name = Column("Village", calculate_fn=get_village_name)

    demonstrations = Column("Number of demonstrations done", key="demonstrations")

    #    worker_type #todo

    children = Column("Number of 0-6 year old children", key="children")

    leaflets = Column("Total number of leaflets distributed", key='leaflets')

    kits = Column("Number of kits sold", key="kits")

class PSISSReport(PSIReport):
    name = "Sensitization Sessions Report"
    exportable = True
    slug = "sensitization_sessions"
    section_name = "sensitization sessions"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictBlockField',]

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain,
            place_types=['state', 'district', "block"], place=self.selected_fixture())

        for c in combos:
            yield [c['state'], c['district'], c["block"]]

    couch_view = 'psi/sensitization'

    default_column_order = (
        'state_name',
        'district_name',
        "block_name",
        'sessions',
        'ayush_doctors',
        "mbbs_doctors",
        "asha_supervisors",
        "ashas",
        "awws",
        "other",
        "attendees",
    )

    state_name = Column("State", calculate_fn=lambda key, _: key[0])

    district_name = Column("District", calculate_fn=lambda key, _: key[1])

    block_name = Column("Block", calculate_fn=lambda key, _: key[2])

    sessions = Column("Number of Sessions", key="sessions")

    ayush_doctors = Column("Ayush Sensitized", key="ayush_doctors")

    mbbs_doctors = Column("MBBS Sensitized", key="mbbs_doctors")

    asha_supervisors = Column("Asha Supervisors Sensitized", key="asha_supervisors")

    ashas = Column("Ashas Sensitized", key="ashas")

    awws = Column("AWW Sensitized", key="awws")

    other = Column("Other Sensitized", key="other")

    attendees = Column("VHND Attendees", key='attendees')

class PSITSReport(PSIReport):
    name = "Training Sessions Report"
    exportable = True
    slug = "training_sessions"
    section_name = "training sessions"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',]

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain,
            place_types=['state', 'district'], place=self.selected_fixture())

        for c in combos:
            yield [c['state'], c['district']]

    couch_view = 'psi/training'

    default_column_order = (
        'state_name',
        'district_name',

        "priv_trained",
        "priv_ayush_trained",
        "priv_allo_trained",
        "priv_avg_diff",
        "priv_gt80",

        "pub_trained",
        "pub_ayush_trained",
        "pub_allo_trained",
        "pub_avg_diff",
        "pub_gt80",

        "dep_trained",
        "dep_pers_trained",
        "dep_avg_diff",
        "dep_gt80",

        "flw_trained",
        "flw_pers_trained",
        "flw_avg_diff",
        "flw_gt80",
    )

    state_name = Column("State", calculate_fn=lambda key, _: key[0])

    district_name = Column("District", calculate_fn=lambda key, _: key[1])

    priv_trained = Column("Private: Number of Trainings", key="priv_trained")
    priv_ayush_trained = Column("Private: Ayush trained", key="priv_ayush_trained")
    priv_allo_trained = Column("Private: Allopathics trained", key="priv_allo_trained")
    priv_avg_diff = Column("Private: Learning changed", key="priv_avg_diff", reduce_fn=mean)
    priv_gt80 = Column("Private: Num > 80%", key="priv_gt80")

    pub_trained = Column("Public: Number of Trainings", key="pub_trained")
    pub_ayush_trained = Column("Public: Ayush trained", key="pub_ayush_trained")
    pub_allo_trained = Column("Public: Allopathics trained", key="pub_allo_trained")
    pub_avg_diff = Column("Public: Learning changed", key="pub_avg_diff", reduce_fn=mean)
    pub_gt80 = Column("Public: Num > 80%", key="pub_gt80")

    dep_trained = Column("Depot: Number of Trainings", key="dep_trained")
    dep_pers_trained = Column("Depot: Number of Personnel Trained", key="dep_pers_trained")
    dep_avg_diff = Column("Depot: Learning changed", key="dep_avg_diff", reduce_fn=mean)
    dep_gt80 = Column("Depot: Num > 80%", key="dep_gt80")

    flw_trained = Column("FLW: Number of Trainings", key="flw_trained")
    flw_pers_trained = Column("FLW: Number of Personnel Trained", key="flw_pers_trained")
    flw_avg_diff = Column("FLW: Learning changed", key="flw_avg_diff", reduce_fn=mean)
    flw_gt80 = Column("FLW: Num > 80%", key="flw_gt80")
