from django.conf import settings

from celery.task import task

from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from custom.icds.location_reassignment.download import Households, OtherCases
from custom.icds.location_reassignment.models import Transition
from custom.icds.location_reassignment.processor import (
    HouseholdReassignmentProcessor,
    OtherCasesReassignmentProcessor,
    Processor,
)
from custom.icds.location_reassignment.utils import (
    get_case_ids_for_reassignment,
    get_supervisor_id,
    notify_failure,
    notify_success,
    reassign_cases,
    reassign_household,
)


@task
def process_location_reassignment(domain, transitions, uploaded_filename, user_email):
    try:
        Processor(domain, transitions).process()
    except Exception as e:
        notify_failure(
            e,
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Failed",
            email=user_email,
            uploaded_filename=uploaded_filename
        )
        raise e
    else:
        notify_success(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}.",
            email=user_email
        )


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def reassign_cases_for_owner(domain, old_location_id, new_location_id, deprecation_time):
    """
    finds relevant case ids and then
    for each household case
        reassign the household case and all its child cases to new location as a group
    and then reassign all other cases as a group
    """

    supervisor_id = get_supervisor_id(domain, old_location_id)
    child_case_ids_per_household_id, other_case_ids = get_case_ids_for_reassignment(domain, old_location_id)

    for household_case_id, household_child_case_ids in child_case_ids_per_household_id.items():
        reassign_household(domain, household_case_id, old_location_id, new_location_id, supervisor_id,
                           deprecation_time=deprecation_time, household_child_case_ids=household_child_case_ids)

    if other_case_ids:
        reassign_cases(domain, other_case_ids, new_location_id)


@task
def email_household_details(domain, transitions, uploaded_filename, user_email):
    try:
        transition_objs = [Transition(**transition) for transition in transitions]
        filestream = Households(domain).dump(transition_objs)
    except Exception as e:
        notify_failure(
            e,
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Household Dump Failed",
            email=user_email,
            uploaded_filename=uploaded_filename
        )
        raise e
    else:
        body = f"The request has been successfully completed for file {uploaded_filename}. "
        if not filestream:
            body += "There were no house hold details found. "
        body += f"Please note that the households are fetched only for " \
                f"{', '.join(Households.valid_operations)}."
        notify_success(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Household Dump Completed",
            body=body,
            email=user_email,
            filestream=filestream,
            filename=f"Households - {uploaded_filename.split('.')[0]}.xlsx"
        )


@task
def email_other_cases_details(domain, transitions, uploaded_filename, user_email):
    try:
        transition_objs = [Transition(**transition) for transition in transitions]
        filestream = OtherCases(domain).dump(transition_objs)
    except Exception as e:
        notify_failure(
            e,
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Other Cases Dump Failed",
            email=user_email,
            uploaded_filename=uploaded_filename
        )
        raise e
    else:
        body = f"The request has been successfully completed for file {uploaded_filename}. "
        if not filestream:
            body += "There were no cases found. "
        body += f"Please note that the cases are fetched only for " \
                f"{', '.join(OtherCases.valid_operations)}."
        notify_success(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Other Cases Dump Completed",
            body=body,
            email=user_email,
            filestream=filestream,
            filename=f"Other Cases - {uploaded_filename.split('.')[0]}.xlsx"
        )


@task
def process_households_reassignment(domain, reassignments, uploaded_filename, user_email):
    try:
        HouseholdReassignmentProcessor(domain, reassignments).process()
    except Exception as e:
        notify_failure(
            e,
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Household Reassignment Failed",
            email=user_email,
            uploaded_filename=uploaded_filename
        )
        raise e
    else:
        notify_success(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Household Reassignment Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}.",
            email=user_email
        )


@task
def process_other_cases_reassignment(domain, reassignments, uploaded_filename, user_email):
    try:
        OtherCasesReassignmentProcessor(domain, reassignments).process()
    except Exception as e:
        notify_failure(
            e,
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Other Cases Reassignment Failed",
            email=user_email,
            uploaded_filename=uploaded_filename
        )
        raise e
    else:
        notify_success(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Other Cases Reassignment Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}.",
            email=user_email
        )


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def process_ucr_changes(domain, case_ids):
    cases = CaseAccessorSQL.get_cases(case_ids)
    docs = [case.to_json() for case in cases]
    data_source_providers = [DynamicDataSourceProvider(), StaticDataSourceProvider()]

    all_configs = [
        source
        for provider in data_source_providers
        for source in provider.by_domain(domain)
    ]

    adapters = [
        get_indicator_adapter(config, raise_errors=True, load_source='location_reassignment')
        for config in all_configs
    ]

    for doc in docs:
        eval_context = EvaluationContext(doc)
        for adapter in adapters:
            if adapter.config.filter(doc, eval_context):
                rows_to_save = adapter.get_all_values(doc, eval_context)
                if rows_to_save:
                    adapter.save_rows(rows_to_save, use_shard_col=False)
                else:
                    adapter.delete(doc, use_shard_col=False)
