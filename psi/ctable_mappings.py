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

class HouseholdMapping(CtableMappingFixture):
    name = "household_demonstrations"
    domains = ['psi-unicef', 'psi']
    couch_view = 'psi/household_demonstrations'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="state", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="block", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="village_code", data_type="integer", value_source="key", value_index=4),
            ColumnDef(name="demo_type", data_type="string", value_source="key", value_index=5),
            ColumnDef(name="date", data_type="datetime", value_source="key", value_index=7),            
        ]
        for c in ['children', 'demonstrations', 'kits', 'leaflets']:
            columns.append(ColumnDef(name=c, data_type="integer", value_source="value", value_attribute='sum',
                                     match_keys=[KeyMatcher(index=6, value=c)]))

        return columns

class SensitizationMapping(CtableMappingFixture):
    name = "sensitization"
    domains = ['psi-unicef', 'psi']
    couch_view = 'psi/sensitization'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="state", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="block", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="date", data_type="datetime", value_source="key", value_index=5),
        ]
        for c in ['sessions', 'ayush_doctors', 'mbbs_doctors', 'asha_supervisors', 'ashas', 'awws', 'other', 'attendees']:
            columns.append(ColumnDef(name=c, data_type="integer", value_source="value", value_attribute='sum',
                                     match_keys=[KeyMatcher(index=4, value=c)]))

        return columns

class TrainingMapping(CtableMappingFixture):
    name = "training"
    domains = ['psi-unicef', 'psi']
    couch_view = 'psi/training'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="state", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="date", data_type="datetime", value_source="key", value_index=4),
        ]
        types = [
            'priv_trained', 'priv_ayush_trained', 'priv_allo_trained', 'priv_avg_diff', 'priv_gt80',
            'pub_trained', 'pub_ayush_trained', 'pub_allo_trained', 'pub_avg_diff', 'pub_gt80',
            'dep_trained', 'dep_pers_trained', 'dep_avg_diff', 'dep_gt80',
            'flw_trained', 'flw_pers_trained', 'flw_avg_diff', 'flw_gt80',
        ]
        for c in types:
            columns.append(ColumnDef(name=c, data_type="integer", value_source="value", value_attribute='sum',
                                     match_keys=[KeyMatcher(index=3, value=c)]))            