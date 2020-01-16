import csv
from custom.icds_reports.models.aggregate import AggAwc
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

domain = "icds-cas"
gujarat_state_id = "3518687a1a6e4b299dedfef967f29c0c"
person_case_type = "person"
rch_id_case_property = "rch_id"

awc_ids = list(
    AggAwc.objects.
        filter(aggregation_level=5, num_launched_awcs=1, month='2020-01-01', state_id=gujarat_state_id).
        values_list('awc_id',flat=True)
)

with open('gujarat_rch_ids.csv', 'w') as _output:
    writer = csv.writer(_output)
    writer.writerow(['Case ID', 'RCH-ID'])

    case_accessor = CaseAccessors(domain)
    for awc_id in with_progress_bar(awc_ids):
        case_ids = case_accessor.get_open_case_ids_in_domain_by_type(person_case_type, [awc_id])
        cases = case_accessor.get_cases(case_ids)
        for case in cases:
            if (case.get_case_property('migration_status') != 'migrated' and
                case.get_case_property('registered_status') != 'not_registered'):
                case_rch_id = case.get_case_property(rch_id_case_property)
                if case_rch_id:
                    writer.writerow([case.case_id, case_rch_id])

