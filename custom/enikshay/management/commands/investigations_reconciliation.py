from collections import defaultdict

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_INVESTIGATION,
)
from custom.enikshay.management.commands.base_model_reconciliation import (
    BaseModelReconciliationCommand,
    DOMAIN,
    get_all_occurrence_case_ids_from_person,
)
from corehq.apps.hqcase.utils import bulk_update_cases

CONFIRMED_DRTB_EPISODE_TYPE = "confirmed_drtb"
DATE_MODIFIED_FIELD = "modified_on"
PROPERTIES_TO_BE_COALESCED = [
    "lft_results",
    "blood_urea_results",
    "other_results",
    "tsh_results",
    "s_cr_results",
    "serum_lipase_results",
    "audiogram_results",
    "urinegravindex_results",
    "ecgqtc_results",
    "electrolyte_results",
    "upt_results",
    "cbcplatelets_results",
    "culture_date",
    "culture_lab_serial_number",
    "culture_result_value",
]


class Command(BaseModelReconciliationCommand):
    email_subject = "Investigations Reconciliation Report"
    result_file_name_prefix = "investigations_reconciliation_report"
    result_file_headers = ([
        "episode_id",
        "investigation_case_id",
        "modified_on",
        "update_or_close"
    ] + PROPERTIES_TO_BE_COALESCED)

    def handle(self, *args, **options):
        # self.commit = options.get('commit')
        self.commit = False
        self.log_progress = options.get('log_progress')
        self.recipient = (options.get('recipient') or 'mkangia@dimagi.com')
        self.recipient = list(self.recipient) if not isinstance(self.recipient, basestring) else [self.recipient]
        self.result_file_name = self.setup_result_file()
        self.case_accessor = CaseAccessors(DOMAIN)
        self.investigation_interval_values = []
        self.person_case_ids = options.get('person_case_ids')
        # iterate all person cases
        for person_case_id in self._get_open_person_case_ids_to_process():
            person_case = self.case_accessor.get_case(person_case_id)
            # check if person is a public app case
            if self.public_app_case(person_case):
                # get all confirmed drtb cases to check for cases under them
                open_confirmed_drtb_episode_cases = get_open_confirmed_drtb_episode_cases(person_case_id)
                for episode_case in open_confirmed_drtb_episode_cases:
                    episode_case_id = episode_case.case_id
                    # get any investigations that need to be reconciled under this episode
                    investigations_to_be_reconciled = self.episode_case_needs_reconciliation(episode_case)
                    if investigations_to_be_reconciled:
                        for interval_type, investigation_cases in investigations_to_be_reconciled.items():
                            self.reconcile_investigation_cases(episode_case_id, investigation_cases)

        self.email_report()

    def reconcile_investigation_cases(self, episode_case_id, investigation_cases):
        # fetch latest investigation case which would retain final values
        latest_investigation_case = sorted(investigation_cases, key=lambda x: x.modified_on)[0]
        retain_case_id = latest_investigation_case.case_id

        properties_by_investigation = defaultdict(dict)
        values_for_property = defaultdict(list)
        investigation_case_modified_on = {}
        coalesced_values = {}

        # iterate over cases to prepare
        # 1. modified on
        # 2. values for all case properties
        # 3. values for all case properties for each investigation case
        for investigation_case in investigation_cases:
            investigation_case_modified_on[investigation_case.case_id] = investigation_case.modified_on
            for case_property in PROPERTIES_TO_BE_COALESCED:
                prop_value = investigation_case.get_case_property(case_property)
                # add value for this investigation under its mapping for writing later
                properties_by_investigation[investigation_case.case_id][case_property] = prop_value
                # add value for this investigation in the collection for values for investigations
                values_for_property[case_property].append(prop_value)

        # iterate over all values for each case property to prepare coalesced values
        for case_property, values in values_for_property.items():
            coalesced_value = self.get_coalesced_value_for_case_property(
                case_property, values
            )
            coalesced_values[case_property] = coalesced_value

        # write values for each investigation
        for investigation_case_id, investigation_case_values in properties_by_investigation.items():
            other_investigation_case_values = investigation_case_values.copy()
            other_investigation_case_values['investigation_case_id'] = investigation_case_id
            other_investigation_case_values['modified_on'] = investigation_case_modified_on[investigation_case_id]
            other_investigation_case_values['episode_id'] = episode_case_id
            other_investigation_case_values['update_or_close'] = (
                'to_be_updated'
                if investigation_case_id == retain_case_id
                else 'to_be_closed'
            )
            self.writerow(other_investigation_case_values)

        # write final coalesced values
        coalesced_investigation_case = coalesced_values.copy()
        coalesced_investigation_case['investigation_case_id'] = retain_case_id
        coalesced_investigation_case['modified_on'] = latest_investigation_case.modified_on
        coalesced_investigation_case['episode_id'] = episode_case_id
        coalesced_investigation_case['update_or_close'] = 'update'
        self.writerow(coalesced_investigation_case)

    def close_or_update_investigation_cases(self, all_cases, retain_case_id, episode_case_id,
                                            investigation_interval, updates):
        all_case_ids = [investigation_case.case_id for investigation_case in all_cases]
        # ToDo: refetch investigation_cases in case the len of set is different from list
        # remove duplicates in case ids to remove so that we don't retain and close
        # the same case by mistake
        all_case_ids = set(all_case_ids)
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)
        for investigation_case in all_cases:
            self.writerow({
                "episode_case_id": episode_case_id,
                "investigation_interval": investigation_interval,
                "investigation_case_id": investigation_case.case_id,
                "modified_on": investigation_case.get_case_property(DATE_MODIFIED_FIELD),
                "updates": updates,
                "update/close": ('update' if investigation_case.case_id == retain_case_id
                                 else 'closed')
            })
        if self.commit:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)

    def get_coalesced_value_for_case_property(self, case_property, all_values):
        #ToDo: write logic for this
        return all_values[0]

    def episode_case_needs_reconciliation(self, episode_case):
        # iterate investigation cases to check if any investigation type has more than 1
        # investigation case added for it
        investigation_cases = get_investigation_cases_from_episode(episode_case)
        investigation_cases_by_interval = defaultdict(list)
        for investigation_case in investigation_cases:
            investigation_case_interval = investigation_case.get_case_property("investigation_interval")
            if investigation_case_interval not in self.investigation_interval_values:
                self.investigation_interval_values.append(investigation_case_interval)
            investigation_cases_by_interval[investigation_case_interval].append(
                investigation_case
            )
        investigation_cases_to_reconcile = {}
        for interval_type, investigation_cases in investigation_cases_by_interval.items():
            if len(investigation_cases) > 1:
                investigation_cases_to_reconcile[interval_type] = investigation_cases

        return investigation_cases_to_reconcile

    def _get_open_person_case_ids_to_process(self):
        if self.person_case_ids:
            num_case_ids = len(self.person_case_ids)
            for i, case_id in enumerate(self.person_case_ids):
                yield case_id
                if i % 1000 == 0 and self.log_progress:
                    print("processed %d / %d docs" % (i, num_case_ids))
        else:
            from corehq.sql_db.util import get_db_aliases_for_partitioned_query
            dbs = get_db_aliases_for_partitioned_query()
            for db in dbs:
                case_ids = (
                    CommCareCaseSQL.objects
                    .using(db)
                    .filter(domain=DOMAIN, type="person", closed=False)
                    .values_list('case_id', flat=True)
                )
                num_case_ids = len(case_ids)
                if self.log_progress:
                    print("processing %d docs from db %s" % (num_case_ids, db))
                for i, case_id in enumerate(case_ids):
                    yield case_id
                    if i % 1000 == 0 and self.log_progress:
                        print("processed %d / %d docs from db %s" % (i, num_case_ids, db))


def get_open_confirmed_drtb_episode_cases(person_case_id):
    occurrence_case_ids = get_all_occurrence_case_ids_from_person(
        person_case_id
    )
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases(occurrence_case_ids)
    open_confirmed_drtb_episode_cases = [
        case for case in all_cases
        if not case.closed
        and case.type == CASE_TYPE_EPISODE
        and case.get_case_property("episode_type") == CONFIRMED_DRTB_EPISODE_TYPE
    ]
    return open_confirmed_drtb_episode_cases


def get_investigation_cases_from_episode(episode_case):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([episode_case.case_id])
    return [case for case in all_cases if case.type == CASE_TYPE_INVESTIGATION]
