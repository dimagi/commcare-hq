from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task
from celery.utils.log import get_task_logger
from django.utils.translation import ugettext as _
from couchdbkit import ResourceConflict, BulkSaveError
from casexml.apps.case.mock import CaseBlock
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.models import UserArchivedRebuild
from corehq.util.log import SensitiveErrorMail
from couchforms.exceptions import UnexpectedDeletedXForm
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime
from soil import DownloadBase
from casexml.apps.case.xform import get_case_ids_from_form

logger = get_task_logger(__name__)


@task(ErrorMail=SensitiveErrorMail)
def bulk_upload_async(domain, user_specs, group_specs, location_specs):
    from corehq.apps.users.bulkupload import create_or_update_users_and_groups
    task = bulk_upload_async
    DownloadBase.set_progress(task, 0, 100)
    results = create_or_update_users_and_groups(
        domain,
        user_specs,
        group_specs,
        location_specs,
        task=task,
    )
    DownloadBase.set_progress(task, 100, 100)
    return {
        'messages': results
    }


@task(rate_limit=2, queue='background_queue', ignore_result=True)  # limit this to two bulk saves a second so cloudant has time to reindex
def tag_cases_as_deleted_and_remove_indices(domain, case_ids, deletion_id, deletion_date):
    from corehq.apps.sms.tasks import delete_phone_numbers_for_owners
    from corehq.apps.reminders.tasks import delete_reminders_for_cases
    CaseAccessors(domain).soft_delete_cases(list(case_ids), deletion_date, deletion_id)
    _remove_indices_from_deleted_cases_task.delay(domain, case_ids)
    delete_phone_numbers_for_owners.delay(case_ids)
    delete_reminders_for_cases.delay(domain, case_ids)


@task(rate_limit=2, queue='background_queue', ignore_result=True, acks_late=True)
def tag_forms_as_deleted_rebuild_associated_cases(user_id, domain, form_id_list, deletion_id,
                                                  deletion_date, deleted_cases=None):
    """
    Upon user deletion, mark associated forms as deleted and prep cases
    for a rebuild.
    - 2 saves/sec for cloudant slowness (rate_limit)
    """
    deleted_cases = deleted_cases or set()
    cases_to_rebuild = set()

    for form in FormAccessors(domain).iter_forms(form_id_list):
        if form.domain != domain:
            continue

        # rebuild all cases anyways since we don't know if this has run or not if the task was killed
        cases_to_rebuild.update(get_case_ids_from_form(form))

    # do this after getting case_id's since iter_forms won't return deleted forms
    FormAccessors(domain).soft_delete_forms(list(form_id_list), deletion_date, deletion_id)

    detail = UserArchivedRebuild(user_id=user_id)
    for case_id in cases_to_rebuild - deleted_cases:
        _rebuild_case_with_retries.delay(domain, case_id, detail)


@task(queue='background_queue', ignore_result=True, acks_late=True)
def _remove_indices_from_deleted_cases_task(domain, case_ids):
    # todo: we may need to add retry logic here but will wait to see
    # what errors we should be catching
    try:
        remove_indices_from_deleted_cases(domain, case_ids)
    except BulkSaveError as e:
        notify_exception(
            None,
            "_remove_indices_from_deleted_cases_task "
            "experienced a BulkSaveError. errors: {!r}".format(e.errors)
        )
        raise


def remove_indices_from_deleted_cases(domain, case_ids):
    from corehq.apps.hqcase.utils import submit_case_blocks
    deleted_ids = set(case_ids)
    indexes_referencing_deleted_cases = CaseAccessors(domain).get_all_reverse_indices_info(list(case_ids))
    case_updates = [
        CaseBlock(
            case_id=index_info.case_id,
            index={
                index_info.identifier: (index_info.referenced_type, '')  # blank string = delete index
            }
        ).as_string(format_datetime=json_format_datetime)
        for index_info in indexes_referencing_deleted_cases
        if index_info.case_id not in deleted_ids
    ]
    submit_case_blocks(case_updates, domain)


@task(bind=True, queue='background_queue', ignore_result=True,
      default_retry_delay=5 * 60, max_retries=3, acks_late=True)
def _rebuild_case_with_retries(self, domain, case_id, detail):
    """
    Rebuild a case with retries
    - retry in 5 min if failure occurs after (default_retry_delay)
    - retry a total of 3 times
    """
    from casexml.apps.case.cleanup import rebuild_case_from_forms
    try:
        rebuild_case_from_forms(domain, case_id, detail)
    except (UnexpectedDeletedXForm, ResourceConflict) as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            notify_exception(
                "Maximum Retries Exceeded while rebuilding case {} during deletion.".format(case_id)
            )


@periodic_task(
    run_every=crontab(hour=23, minute=55),
    queue='background_queue',
)
def resend_pending_invitations():
    from corehq.apps.users.models import Invitation
    days_to_resend = (15, 29)
    days_to_expire = 30
    domains = Domain.get_all()
    for domain in domains:
        invitations = Invitation.by_domain(domain.name)
        for invitation in invitations:
            days = (datetime.utcnow() - invitation.invited_on).days
            if days in days_to_resend:
                invitation.send_activation_email(days_to_expire - days)


@task
def turn_on_demo_mode_task(couch_user, domain):
    from corehq.apps.ota.utils import turn_on_demo_mode

    DownloadBase.set_progress(turn_on_demo_mode_task, 0, 100)
    results = turn_on_demo_mode(couch_user, domain)
    DownloadBase.set_progress(turn_on_demo_mode_task, 100, 100)

    return {
        'messages': results
    }


@task
def reset_demo_user_restore_task(couch_user, domain):
    from corehq.apps.ota.utils import reset_demo_user_restore

    DownloadBase.set_progress(reset_demo_user_restore_task, 0, 100)

    try:
        reset_demo_user_restore(couch_user, domain)
        results = {'errors': []}
    except Exception as e:
        notify_exception(None, message=e.message)
        results = {'errors': [
            _("Something went wrong in creating restore for the user. Please try again or report an issue")
        ]}

    DownloadBase.set_progress(reset_demo_user_restore_task, 100, 100)
    return {'messages': results}
