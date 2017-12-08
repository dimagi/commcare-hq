from django.core.management.base import CommandError
from django.utils.dateparse import parse_date
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_EPISODE,
    get_occurrence_case_from_episode)
from custom.enikshay.management.commands.base_model_reconciliation import (
    BaseModelReconciliationCommand,
    DOMAIN,
)


class Command(BaseModelReconciliationCommand):
    """
    1. If an open person case has multiple open occurrence cases
       we need to keep one which is relevant and close others
    2. If an open occurrence case has multiple open episode cases with
       case property is_active = "yes", we need to reconcile them
    """
    email_subject = "Occurrence and Episode Reconciliation Report"
    result_file_name_prefix = "duplicate_occurrence_and_episode_reconciliation_report"
    result_file_headers = [
        "case_type",
        "associated_case_id",
        "retain_case_id",
        "closed_case_ids",
        "closed_extension_case_ids",
        "retained_case_date_opened",
        "retained_case_episode_type",
        "retained_case_is_active",
        "closed_cases_details",
        "notes"
    ]

    def handle(self, *args, **options):
        self.commit = options.get('commit')
        self.log_progress = options.get('log_progress')
        self.recipient = (options.get('recipient') or 'mkangia@dimagi.com')
        self.recipient = list(self.recipient) if not isinstance(self.recipient, basestring) else [self.recipient]
        self.result_file_name = self.setup_result_file()
        self.case_accessor = CaseAccessors(DOMAIN)
        self.person_case_ids = options.get('person_case_ids')
        # iterate all person cases
        for person_case_id in self._get_open_person_case_ids_to_process():
            person_case = self.case_accessor.get_case(person_case_id)
            if self.public_app_case(person_case):
                open_occurrence_cases = get_open_occurrence_cases_for_person(person_case_id)
                if len(open_occurrence_cases) > 1:
                    # reconcile occurrence cases
                    # also reconcile episode cases under these if needed
                    self.reconcile_cases(open_occurrence_cases, person_case_id)
                elif open_occurrence_cases:
                    # if needed reconcile episode cases under the open occurrence case
                    self.get_open_active_reconciled_episode_cases_for_occurrence(open_occurrence_cases[0].get_id)

        self.email_report()

    def get_relevant_episode_case(self, open_active_episode_cases):
        """
            For each episode, use the following priority order to identify which case to keep (single)
                episode_type = confirmed_drtb
                episode_type = confirmed_tb
                get_relevant_episode_case_by_dates
        """
        open_active_confirmed_drtb_episode_cases = []
        open_active_confirmed_tb_episode_cases = []
        for episode_case in open_active_episode_cases:
            episode_type = episode_case.get_case_property('episode_type')
            if episode_type == 'confirmed_drtb':
                open_active_confirmed_drtb_episode_cases.append(episode_case)
            elif episode_type == 'confirmed_tb':
                open_active_confirmed_tb_episode_cases.append(episode_case)

        open_active_confirmed_drtb_episode_cases_count = len(open_active_confirmed_drtb_episode_cases)
        open_active_confirmed_tb_episode_cases_count = len(open_active_confirmed_tb_episode_cases)

        # Only one active case found with confirmed drtb
        if open_active_confirmed_drtb_episode_cases_count == 1:
            return open_active_confirmed_drtb_episode_cases[0]

        elif open_active_confirmed_drtb_episode_cases_count > 1:
            return get_relevant_episode_case_by_dates(open_active_confirmed_drtb_episode_cases,
                                                      log_progress=self.log_progress)
        elif open_active_confirmed_tb_episode_cases_count == 1:
            return open_active_confirmed_tb_episode_cases[0]
        elif open_active_confirmed_tb_episode_cases_count > 1:
            return get_relevant_episode_case_by_dates(open_active_confirmed_tb_episode_cases,
                                                      log_progress=self.log_progress)
        else:
            return get_relevant_episode_case_by_dates(open_active_episode_cases, log_progress=self.log_progress)

    def reconcile_cases(self, open_occurrence_cases, person_case_id):
        """
        Find the occurrence with most relevant reconciled(if needed) episode case
        """
        open_occurrence_case_ids = [case.case_id for case in open_occurrence_cases]
        # get reconciled(if needed) episode cases for all open occurrences
        all_open_active_episode_cases_for_person = []
        for open_occurrence_case_id in open_occurrence_case_ids:
            all_open_active_episode_cases_for_person += self.get_open_active_reconciled_episode_cases_for_occurrence(
                open_occurrence_case_id)
        if all_open_active_episode_cases_for_person:
            relevant_episode_case = self.get_relevant_episode_case(all_open_active_episode_cases_for_person)
            retain_case = get_occurrence_case_from_episode(DOMAIN, relevant_episode_case)
            self.close_cases(open_occurrence_cases, retain_case, person_case_id, "occurrence")
        else:
            # Log the case where no open and active episode case was found for reconciliation
            # This should imply a person with multiple open occurrence cases but none of them with
            # an open and active episode case to consider
            self.writerow({
                "case_type": "occurrence",
                "associated_case_id": person_case_id,
                "notes": "Found no active open episodes cases to reconcile occurrences for this person"
            })

    def close_cases(self, all_cases, retain_case, associated_case_id, reconciling_case_type):
        # remove duplicates in case ids to remove so that we don't retain and close
        # the same case by mistake
        all_case_ids = set([case.case_id for case in all_cases])
        retain_case_id = retain_case.case_id
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)

        case_accessor = CaseAccessors(DOMAIN)
        closing_extension_case_ids = case_accessor.get_extension_case_ids(case_ids_to_close)

        self.writerow({
            "case_type": reconciling_case_type,
            "associated_case_id": associated_case_id,
            "retain_case_id": retain_case_id,
            "closed_case_ids": ','.join(map(str, case_ids_to_close)),
            "closed_extension_case_ids": ','.join(map(str, closing_extension_case_ids)),
            "retained_case_date_opened": str(retain_case.opened_on),
            "retained_case_episode_type": retain_case.get_case_property("episode_type"),
            "retained_case_is_active": retain_case.get_case_property("is_active"),
            "closed_cases_details": (
                {
                    a_case.case_id: {
                        "last_modified_at(utc)": str(last_user_edit_at(a_case)),
                        "episode_type": a_case.get_case_property("episode_type"),
                        "is_active": a_case.get_case_property("is_active")
                    }
                    for a_case in all_cases
                    if a_case.case_id != retain_case_id
                }
            )
        })
        if self.commit:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)

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

    def reconcile_open_active_episode_cases_for_occurrence(self, open_active_episode_cases, occurrence_case_id):
        retain_case = self.get_relevant_episode_case(open_active_episode_cases)
        self.close_cases(open_active_episode_cases, retain_case, occurrence_case_id, 'episode')

    def get_open_active_reconciled_episode_cases_for_occurrence(self, occurrence_case_id):
        def _get_open_episode_cases_for_occurrence(occurrence_case_id):
            all_cases = self.case_accessor.get_reverse_indexed_cases([occurrence_case_id])
            return [case for case in all_cases
                    if not case.closed and case.type == CASE_TYPE_EPISODE]

        def _get_open_active_episode_cases(episode_cases):
            return [open_episode_case
                    for open_episode_case in episode_cases
                    if open_episode_case.get_case_property('is_active') == 'yes']

        all_open_episode_cases = _get_open_episode_cases_for_occurrence(occurrence_case_id)
        open_active_episode_cases_for_occurrence = _get_open_active_episode_cases(all_open_episode_cases)

        # if there are multiple active open episode cases, reconcile them first
        if len(open_active_episode_cases_for_occurrence) > 1:
            self.reconcile_open_active_episode_cases_for_occurrence(open_active_episode_cases_for_occurrence,
                                                                    occurrence_case_id)

        if self.commit:
            # just confirm again that the episodes were reconciled well
            all_open_episode_cases = _get_open_episode_cases_for_occurrence(occurrence_case_id)
            open_active_episode_cases_for_occurrence = _get_open_active_episode_cases(all_open_episode_cases)
            if len(open_active_episode_cases_for_occurrence) > 1:
                raise CommandError("Resolved open active episode cases were not resolved for occurrence, %s" %
                                   occurrence_case_id)

        return all_open_episode_cases


def last_user_edit_at(case):
    for action in reversed(case.actions):
        form = action.form
        if form and form.user_id and form.user_id != 'system':
            return form.metadata.timeEnd


def get_relevant_episode_case_by_dates(all_cases, log_progress=False):
    episodes_with_treatment_completed_on_earliest_date = []
    treatment_completed_earliest_date = None
    for episode_case in all_cases:
        episode_treatment_completed_on = episode_case.get_case_property('treatment_card_completed_date')
        if not treatment_completed_earliest_date and episode_treatment_completed_on:
            # found first case with treatment_card_completed_date
            # so just consider this as the first ever completed case
            treatment_completed_earliest_date = parse_date(episode_treatment_completed_on)
            episodes_with_treatment_completed_on_earliest_date = [episode_case]
        elif treatment_completed_earliest_date and episode_treatment_completed_on:
            episode_treatment_completed_on = parse_date(episode_treatment_completed_on)
            # found a case with date earlier than we considered before.
            # So just clean up all episode cases considered earlier
            if episode_treatment_completed_on < treatment_completed_earliest_date:
                treatment_completed_earliest_date = episode_treatment_completed_on
                episodes_with_treatment_completed_on_earliest_date = [episode_case]
            # found a case with same treatment_card_completed_date we considered earliest
            # So just add to episode cases considered earlier
            elif episode_treatment_completed_on == treatment_completed_earliest_date:
                episodes_with_treatment_completed_on_earliest_date.append(episode_case)

    # we found one case that have treatment card filled the earliest
    if len(episodes_with_treatment_completed_on_earliest_date) == 1:
        return episodes_with_treatment_completed_on_earliest_date[0]
    # we found multiple cases that have treatment card filled on the earliest same day
    # so just get the one recently user edited from these ones
    elif len(episodes_with_treatment_completed_on_earliest_date) > 1:
        return get_case_recently_modified_on_phone(episodes_with_treatment_completed_on_earliest_date,
                                                   log_progress=log_progress)
    # no case found with treatment_card_completed_date set
    # so just get the recently user edit case
    else:
        return get_case_recently_modified_on_phone(all_cases, log_progress=log_progress)


def get_case_recently_modified_on_phone(all_cases, log_progress):
    recently_modified_case = None
    recently_modified_time = None
    for case in all_cases:
        last_user_edit_on_phone = last_user_edit_at(case)
        if last_user_edit_on_phone:
            if recently_modified_time is None:
                recently_modified_time = last_user_edit_on_phone
                recently_modified_case = case
            elif recently_modified_time and recently_modified_time < last_user_edit_on_phone:
                recently_modified_time = last_user_edit_on_phone
                recently_modified_case = case
            elif (recently_modified_time and recently_modified_time == last_user_edit_on_phone
                    and log_progress):
                print("This looks like a super edge case that can be looked at. "
                      "Not blocking as of now. Case id: {case_id}".format(case_id=case.case_id))

    return recently_modified_case


def get_open_occurrence_cases_for_person(person_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_OCCURRENCE]
