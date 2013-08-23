from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.basic import Column, FunctionView, SummingTabularReport, BasicTabularReport
from corehq.apps.reports.fields import AsyncDrillableField, ReportSelectField
from util import get_unique_combinations
from couchdbkit_aggregate.fn import mean, min, max
from dimagi.utils.decorators.memoized import memoized

class AsyncTestField(AsyncDrillableField):
    label = "Disease/Test Type"
    slug = "test_type"
    hierarchy = [{"type": "diseases", "display": "disease_name"},
                 {"type": "tests", "parent_ref": "disease_id", "references": "test_name", "display": "visible_test_name"}]

class AsyncClinicField(AsyncDrillableField):
    label = "Country/Province/District/Clinic"
    slug = "clinic"
    hierarchy = [{"type": "country", "display": "country_name"},
                 {"type": "province", "parent_ref": "country_id", "references": "country_id", "display": "province_name"},
                 {"type": "district", "parent_ref": "province_id", "references": "province_id", "display": "district_name"},
                 {"type": "clinic", "parent_ref": "district_id", "references": "district_id", "display": "clinic_name"}]


@memoized
def get_village_fdt(domain):
    return FixtureDataType.by_domain_tag(domain, 'village').one()

@memoized
def get_village(req, id):
    village_fdt = get_village_fdt(req.domain)
    return FixtureDataItem.by_field_value(req.domain, village_fdt, 'id', float(id)).one()

def get_village_name(key, req):
    return get_village(req, key[4]).fields.get("name", id)

def get_village_class(key, req):
    return get_village(req, key[4]).fields.get("village_class", "No data")

class GSIDExReport(SummingTabularReport, CustomProjectReport, DatespanMixin):
    is_cacheable = True
    update_after = True
    fields = ['corehq.apps.reports.fields.DatespanField','GSID.reports.AsyncClinicField',]

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


class GSIDReport(BasicTabularReport, CustomProjectReport, DatespanMixin):
    name = "My Basic Report"
    slug = "my_basic_report"
    fields = ['custom.apps.gsid.reports.AsyncTestField', DatespanMixin.datespan_field, 'custom.apps.gsid.reports.AsyncClinicField']

    couch_view = 'gsid/patient_summary'    
    @property
    def keys(self):
        return [[self.domain, 'female', "highpoint"], [self.domain, 'male', "highpoint"]]

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def default_column_order(self):
        return ('clinic_name', 'gender', 'min_age', 'max_age')

    clinic_name = Column("Clinic", calculate_fn=lambda key, _: key[2])
    min_age = Column("Min Age", key="num", reduce_fn=min)
    max_age = Column("Max Age", key="num", reduce_fn=max)
    gender = Column("Gender", calculate_fn=lambda key, _: key[1])


    """    
    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Col A"),
                                DataTablesColumnGroup("Goup 1", DataTablesColumn("Col B"),
                                                      DataTablesColumn("Col C")),
                                DataTablesColumn("Col D"))

    @property
    def rows(self):
        return [
            ['Row 1', 2, 3, 4],
            ['Row 2', 3, 2, 1]
        ]
    """