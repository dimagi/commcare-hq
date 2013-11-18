from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.basic import Column, FunctionView, SummingTabularReport
from corehq.apps.reports.fields import AsyncDrillableField, ReportSelectField
from util import get_unique_combinations
from couchdbkit_aggregate.fn import mean
from dimagi.utils.decorators.memoized import memoized

DEMO_TYPES = ["asha", "aww", "anm", "ngo", "cbo", "vhnd"]

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


class DemoTypeField(ReportSelectField):
    slug = "demo_type"
    name = "Worker Type"
    cssId = "demo_type_select"
    cssClasses = "span6"
    default_option = "Aggregate"

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        self.options = [{'val': '_all', 'text': 'All worker types'}] + [{'val': dt, 'text': dt} for dt in DEMO_TYPES]

class AggregateAtField(ReportSelectField):
    """
        To Use: SUbclass and specify what the field options should be
    """
    slug = "aggregate_at"
    name = "Aggregate at what level"
    cssId = "aggregate_at_select"
    cssClasses = "span6"
    # default_option = "All Worker Types"

    @property
    def default_option(self):
        return "Default: %s" % self.field_opts[-1]

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        self.options = [{'val': f.lower(), 'text': f} for f in [fo for fo in self.field_opts if fo != self.selected]]

class AASD(AggregateAtField):
    field_opts = ["State", "District"]

class AASDB(AggregateAtField):
    field_opts = ["State", "District", "Block"]

class AASDBV(AggregateAtField):
    field_opts = ["State", "District", "Block", "Village"]

@memoized
def get_village_fdt(domain):
    return FixtureDataType.by_domain_tag(domain, 'village').one()

@memoized
def get_village(req, id):
    village_fdt = get_village_fdt(req.domain)
    return FixtureDataItem.by_field_value(req.domain, village_fdt, 'id', float(id)).one()

def get_village_name(key, req):
    return get_village(req, key[4]).fields_without_attributes.get("name", id)

def get_village_class(key, req):
    return get_village(req, key[4]).fields_without_attributes.get("village_class", "No data")

class PSIReport(SummingTabularReport, CustomProjectReport, DatespanMixin):
    is_cacheable = True
    update_after = True
    fields = ['corehq.apps.reports.fields.DatespanField','psi.reports.AsyncPlaceField',]

    state_name = Column("State", calculate_fn=lambda key, _: key[1])

    district_name = Column("District", calculate_fn=lambda key, _: key[2])

    block_name = Column("Block", calculate_fn=lambda key, _: key[3])

    village_name = Column("Village", calculate_fn=get_village_name)

    village_code = Column("Village Code", calculate_fn=lambda key, _: key[4])

    village_class = Column("Village Class", calculate_fn =get_village_class)

    def selected_fixture(self):
        fixture = self.request.GET.get('fixture_id', "")
        return fixture.split(':') if fixture else None

    @property
    @memoized
    def place_types(self):
        opts = ['state', 'district', 'block', 'village']
        agg_at = self.request.GET.get('aggregate_at', None)
        agg_at = agg_at if agg_at and opts.index(agg_at) <= opts.index(self.default_aggregation) else self.default_aggregation
        return opts[:opts.index(agg_at) + 1]

    @property
    def initial_column_order(self):
        ret = tuple([col + '_name' for col in self.place_types[:3]])
        if len(self.place_types) > 3:
            ret += ('village_name', 'village_code', 'village_class')
        return ret

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=self.place_types, place=self.selected_fixture())
        for c in combos:
            yield [self.domain] + [c[pt] for pt in self.place_types]


class PSIEventsReport(PSIReport):
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',
              'psi.reports.AASD',]
    name = "Event Demonstration Report"
    exportable = True
    emailable = True
    slug = "event_demonstations"
    section_name = "event demonstrations"
    default_aggregation = 'district'

    couch_view = 'psi/events'

    @property
    def default_column_order(self):
        return self.initial_column_order + (
        'events',
        'males',
        'females',
        'attendees',
        'leaflets',
        'gifts',
    )

    events = Column("Number of events", key='events')

    males = Column("Number of male attendees", key='males')

    females = Column("Number of female attendees", key='females')

    attendees = Column("Total number of attendees", key='attendees')

    leaflets = Column("Total number of leaflets distributed", key='leaflets')

    gifts = Column("Total number of gifts distributed", key='gifts')


class PSIHDReport(PSIReport):
    name = "Household Demonstrations Report"
    exportable = True
    emailable = True
    slug = "household_demonstations"
    section_name = "household demonstrations"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.AsyncPlaceField',
              'psi.reports.DemoTypeField',
              'psi.reports.AASDBV',]
    default_aggregation = 'village'

    def __init__(self, request, **kwargs):
        """
            This is necessary because the demo_type column's calculate_functions needs to have information from the
            request. (to determine place types) Since columns are only initialized when the class is defined (using the
            ColumnCollector metaclass), the demo_type column needs to be initialized here when it has access to request
        """
        super(PSIHDReport, self).__init__(request, **kwargs)
        calculate_fn = lambda key, _: key[len(self.place_types) + 1]
        self.columns['demo_type'] = Column("Worker Type", calculate_fn=calculate_fn)
        self.columns['demo_type'].view = FunctionView(calculate_fn=calculate_fn)
        self.function_views['demo_type'] = self.columns['demo_type'].view

    @property
    @memoized
    def selected_dt(self):
        return self.request.GET.get('demo_type', "")

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=self.place_types, place=self.selected_fixture())
        selected_demo_type = self.request.GET.get('demo_type', "")
        for c in combos:
            if self.selected_dt:
                if self.selected_dt == '_all':
                    for dt in DEMO_TYPES:
                        yield [self.domain] + [c[pt] for pt in self.place_types] + [dt]
                else:
                    yield [self.domain] + [c[pt] for pt in self.place_types] + [selected_demo_type]
            else:
                yield [self.domain] + [c[pt] for pt in self.place_types]

    couch_view = 'psi/household_demonstrations'

    @property
    def default_column_order(self):
        to_add = [
            'demonstrations',
            'children',
            'leaflets',
            'kits',
        ]
        if self.selected_dt:
            to_add.insert(0, "demo_type")
        return self.initial_column_order + tuple(to_add)


    demo_type = Column("Worker Type", calculate_fn=lambda key, _: key[5])

    demonstrations = Column("Number of demonstrations done", key="demonstrations")

    children = Column("Number of 0-6 year old children", key="children")

    leaflets = Column("Total number of leaflets distributed", key='leaflets')

    kits = Column("Number of kits sold", key="kits")

class PSISSReport(PSIReport):
    name = "Sensitization Sessions Report"
    exportable = True
    emailable = True
    slug = "sensitization_sessions"
    section_name = "sensitization sessions"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictBlockField',
              'psi.reports.AASDB',]
    default_aggregation = 'block'

    couch_view = 'psi/sensitization'

    @property
    def default_column_order(self):
        return self.initial_column_order + (
            'sessions',
            'ayush_doctors',
            "mbbs_doctors",
            "asha_supervisors",
            "ashas",
            "awws",
            "other",
            "attendees",
        )

    sessions = Column("Number of Sessions", key="sessions")

    ayush_doctors = Column("Ayush Sensitized", key="ayush_doctors")

    mbbs_doctors = Column("MBBS Sensitized", key="mbbs_doctors")

    asha_supervisors = Column("Asha Supervisors Sensitized", key="asha_supervisors")

    ashas = Column("Ashas Sensitized", key="ashas")

    awws = Column("AWW Sensitized", key="awws")

    other = Column("Others (ANM, MPW, etc.)", key="other")

    attendees = Column("VHND Attendees", key='attendees')

class PSITSReport(PSIReport):
    name = "Training Sessions Report"
    exportable = True
    emailable = True
    slug = "training_sessions"
    section_name = "training sessions"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',
              'psi.reports.AASD',]
    default_aggregation = 'district'

    couch_view = 'psi/training'

    @property
    def default_column_order(self):
        return self.initial_column_order + (
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
