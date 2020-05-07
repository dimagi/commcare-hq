from django.conf import settings
from django.core.mail.message import EmailMessage
from django.template.defaultfilters import linebreaksbr

from celery.task import task

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import SYSTEM_USER_ID, normalize_username
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from custom.icds.location_reassignment.download import Households
from custom.icds.location_reassignment.exceptions import InvalidUserTransition
from custom.icds.location_reassignment.processor import (
    HouseholdReassignmentProcessor,
    Processor,
)
from custom.icds.location_reassignment.utils import (
    get_household_case_ids,
    get_supervisor_id,
    reassign_household_case,
)


@task
def process_location_reassignment(domain, transitions, uploaded_filename, user_email):
    try:
        Processor(domain, transitions).process()
    except Exception as e:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Failed",
            body=linebreaksbr(
                f"The request could not be completed for file {uploaded_filename}. Something went wrong.\n"
                f"Error raised : {e}.\n"
                "Please report an issue if needed."
            ),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.content_subtype = "html"
        email.send()
        raise e
    else:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}.",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def reassign_household_and_child_cases_for_owner(domain, old_location_id, new_location_id, deprecation_time):
    """
    finds all household cases assigned to the old location and then
    reassign the household case and all its child cases to new location
    """
    supervisor_id = get_supervisor_id(domain, old_location_id)
    household_case_ids = get_household_case_ids(domain, old_location_id)

    for household_case_id in household_case_ids:
        reassign_household_case(domain, household_case_id, old_location_id, new_location_id, supervisor_id,
                                deprecation_time)


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def update_usercase(domain, old_username, new_username):
    if "@" not in old_username:
        old_username = normalize_username(old_username, domain)
    if "@" not in new_username:
        new_username = normalize_username(new_username, domain)
    old_user = CouchUser.get_by_username(old_username)
    new_user = CouchUser.get_by_username(new_username)
    if old_user and new_user and old_user.is_commcare_user() and new_user.is_commcare_user():
        old_user_usercase = old_user.get_usercase()
        new_user_usercase = new_user.get_usercase()
        # pick values that are not already present on the new user's usercase, populated already via HQ
        updates = {}
        for key in set(old_user_usercase.case_json.keys()) - set(new_user_usercase.case_json.keys()):
            updates[key] = old_user_usercase.case_json[key]
        if updates:
            case_block = CaseBlock(new_user_usercase.case_id,
                                   update=old_user_usercase.case_json,
                                   user_id=SYSTEM_USER_ID).as_text()
            submit_case_blocks([case_block], domain, user_id=SYSTEM_USER_ID)
    else:
        raise InvalidUserTransition("Invalid Transition with old user %s and new user %s" % (
            old_username, new_username
        ))


@task
def email_household_details(domain, transitions, uploaded_filename, user_email):
    try:
        filestream = Households(domain).dump(transitions)
    except Exception as e:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Household Dump Failed",
            body=linebreaksbr(
                f"The request could not be completed for file {uploaded_filename}. Something went wrong.\n"
                f"Error raised : {e}.\n"
                "Please report an issue if needed."
            ),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.content_subtype = "html"
        email.send()
        raise e
    else:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Location Reassignment Household Dump Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}. ",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        if filestream:
            email.attach(filename="Households.xlsx", content=filestream.read())
        else:
            email.body += "There were no house hold details found. "
        email.body += f"Please note that the households are fetched only for " \
                      f"{', '.join(Households.valid_operations)}."
        email.send()


@task
def process_households_reassignment(domain, reassignments, uploaded_filename, user_email):
    try:
        HouseholdReassignmentProcessor(domain, reassignments).process()
    except Exception as e:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Household Reassignment Failed",
            body=linebreaksbr(
                f"The request could not be completed for file {uploaded_filename}. Something went wrong.\n"
                f"Error raised : {e}.\n"
                "Please report an issue if needed."
            ),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.content_subtype = "html"
        email.send()
        raise e
    else:
        email = EmailMessage(
            subject=f"[{settings.SERVER_ENVIRONMENT}] - Household Reassignment Completed",
            body=f"The request has been successfully completed for file {uploaded_filename}.",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()


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

    async_configs_by_doc_id = {}
    for doc in docs:
        eval_context = EvaluationContext(doc)
        for adapter in adapters:
            if adapter.config.filter(doc, eval_context):
                async_configs_by_doc_id[doc['_id']].append(adapter.config._id)
                rows_to_save = adapter.get_all_values(doc, eval_context)
                if rows_to_save:
                    adapter.save_rows(rows_to_save, use_shard_col=False)
                else:
                    adapter.delete(doc, use_shard_col=False)
