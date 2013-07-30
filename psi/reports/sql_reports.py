from sqlagg.columns import *
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn, SummingSqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from util import get_unique_combinations
from dimagi.utils.decorators.memoized import memoized


class PSISQLReport(SummingSqlTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.DatespanField','psi.reports.AsyncPlaceField',]

    @property
    def group_by(self):
        return [col.view.key for col in self.initial_columns[:4]]

    @property
    def filter_values(self):
        return dict(domain=self.domain,
                    startdate=self.datespan.startdate_param_utc,
                    enddate=self.datespan.enddate_param_utc)

    @property
    def filters(self):
        return ["domain = :domain", "date between :startdate and :enddate"]

    @property
    def keys(self):
        combos = get_unique_combinations(self.domain, place_types=self.place_types, place=self.selected_fixture())
        for c in combos:
            yield [c[pt] for pt in self.place_types]

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
    def initial_columns(self):
        initial_cols = dict(state_name=DatabaseColumn("State", SimpleColumn('state')),
                            district_name=DatabaseColumn("District", SimpleColumn('district')),
                            block_name=DatabaseColumn("Block", SimpleColumn('block')),
                            village_name=DatabaseColumn("Village", SimpleColumn('village_id'),
                                                        format_fn=self.get_village_name),
                            village_code=DatabaseColumn("Village Code", SimpleColumn('village_code')),
                            village_class=DatabaseColumn("Village Class", SimpleColumn('village_class'),
                                                         format_fn=self.get_village_class))
        ret = tuple([col + '_name' for col in self.place_types[:3]])
        if len(self.place_types) > 3:
            ret += ('village_name', 'village_code', 'village_class')
        return [initial_cols[col] for col in ret]

    @memoized
    def get_village(self, id):
        village_fdt = self.get_village_fdt(self.domain)
        return FixtureDataItem.by_field_value(self.domain, village_fdt, 'id', float(id)).one()

    def get_village_name(self, village_id):
        return self.get_village(village_id).fields.get("name", id)

    def get_village_class(self, village_id):
        return self.get_village(village_id).fields.get("village_class", "No data")


class PSISQLEventsReport(PSISQLReport):
    fields = ['corehq.apps.reports.fields.DatespanField',
              'psi.reports.StateDistrictField',
              'psi.reports.AASD',]
    name = "Event Demonstration Report"
    exportable = True
    emailable = True
    slug = "event_demonstations_sql"
    section_name = "event demonstrations"
    default_aggregation = 'district'
    table_name = 'psi-unicef_psi_events'

    @property
    def columns(self):
        return self.initial_columns + [
            DatabaseColumn("Number of events", SumColumn('events')),
            DatabaseColumn("Number of male attendees", SumColumn('males')),
            DatabaseColumn("Number of female attendees", SumColumn('females')),
            DatabaseColumn("Total number of attendees", SumColumn('attendees')),
            DatabaseColumn("Total number of leaflets distributed", SumColumn('leaflets')),
            DatabaseColumn("Total number of gifts distributed", SumColumn('gifts'))
        ]