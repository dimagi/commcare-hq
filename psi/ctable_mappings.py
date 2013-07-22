from ctable.fixtures import CtableMappingFixture
from ctable.models import ColumnDef, KeyMatcher


class EventsMapping(CtableMappingFixture):
    name = 'events'
    domains = ['psi-unicef', 'psi']
    couch_view = 'psi/events'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="state", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=4),
            ColumnDef(name="date", data_type="date", value_source="key", value_index=1),
        ]
        for c in ['events', 'males', 'females', 'attendees', 'leaflets', 'gifts']:
            columns.append(ColumnDef(name=c, data_type="integer", value_source="value", value_attribute='sum',
                                     match_keys=[KeyMatcher(index=5, value=c)]))

        return columns

    def customize(self, mapping):
        mapping.couch_key_prefix = ['ctable']
