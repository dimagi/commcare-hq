from ctable.fixtures import CtableMappingFixture
from ctable.models import ColumnDef, KeyMatcher


class PatientSummaryMapping(CtableMappingFixture):
    name = 'patient_summary'
    domains = ['gsid']
    couch_view = 'gsid/patient_summary'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="disease_name", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="test_version", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="province", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=4),
            ColumnDef(name="clinic", data_type="string", value_source="key", value_index=5),
            ColumnDef(name="gender", data_type="string", value_source="key", value_index=6),
            ColumnDef(name="date", data_type="date", value_source="key", value_index=1),
            ColumnDef(name="age", data_type="integer", value_source="value", value_attribute="sum", 
                      match_keys=[KeyMatcher(index=7, value="age")]),
            ColumnDef(name="diagnosis", data_type="string", value_source="value", value_attribute="sum", 
                      match_keys=[KeyMatcher(index=7, value="diagnosis")])         

        ]

        return columns

class ResultsByDayMapping(CtableMappingFixture):
    name = "results_by_day"
    domains = ['gsid']
    couch_view = 'gsid/results_by_day'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="disease_name", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="test_version", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="province", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=4),
            ColumnDef(name="clinic", data_type="string", value_source="key", value_index=5),
            ColumnDef(name="gender", data_type="string", value_source="key", value_index=6),
            ColumnDef(name="date", data_type="date", value_source="key", value_index=7),
        ]

        return columns

class TestLotsMapping(CtableMappingFixture):
    name = "test_lots"
    domains = ['gsid']
    couch_view = 'gsid/test_lots'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="disease_name", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="test_version", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="province", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=4),
            ColumnDef(name="clinic", data_type="string", value_source="key", value_index=5),
            ColumnDef(name="date", data_type="string", value_source="key", value_index=6),
            ColumnDef(name="lot_number", data_type="integer", value_source="key", value_index=7),
        ]

        return columns

class ResultsByAgeMapping(CtableMappingFixture):
    name = "results_by_age"
    domains = ['gsid']
    couch_view = 'gsid/results_by_age'
    schedule_active = True

    @property
    def columns(self):
        columns = [
            ColumnDef(name="domain", data_type="string", value_source="key", value_index=0),
            ColumnDef(name="disease_name", data_type="string", value_source="key", value_index=1),
            ColumnDef(name="test_version", data_type="string", value_source="key", value_index=2),
            ColumnDef(name="province", data_type="string", value_source="key", value_index=3),
            ColumnDef(name="district", data_type="string", value_source="key", value_index=4),
            ColumnDef(name="clinic", data_type="string", value_source="key", value_index=5),
            ColumnDef(name="gender", data_type="string", value_source="key", value_index=6),
            ColumnDef(name="date", data_type="date", value_source="key", value_index=7),
            ColumnDef(name="age", data_type="integer", value_source="key", value_index=8),
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

        return columns        