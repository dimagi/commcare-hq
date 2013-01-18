from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.basic import BasicTabularReport, Column
from corehq.apps.reports.fields import AsyncDrillableField
from dimagi.utils.decorators.memoized import memoized
from util import get_unique_combinations, psi_training_sessions

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
    return village_fdi.fields.get("name", id) if village_fdi else id

class PSIHDReport(PSIReport):
    name = "Household Demonstrations Report"
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

    ayush_doctors = Column("Ayush Trained", key="ayush_doctors")

    mbbs_doctors = Column("MBBS Trained", key="mbbs_doctors")

    asha_supervisors = Column("Asha Supervisors Trained", key="asha_supervisors")

    ashas = Column("Ashas trained", key="ashas")

    awws = Column("AWW Trained", key="awws")

    other = Column("Other Trained", key="other")

    attendees = Column("VHND Attendees", key='attendees')

class PSITSReport(PSIReport):
    name = "Training Sessions Report"
    slug = "training_sessions"
    section_name = "training sessions"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',]

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
        hh_data = psi_training_sessions(self.domain, {}, place=self.selected_fixture(),
            startdate=self.datespan.startdate_param_utc, enddate=self.datespan.enddate_param_utc)
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
