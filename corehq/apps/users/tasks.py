from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task
from celery.utils.log import get_task_logger
from couchdbkit import ResourceConflict
from corehq.util.log import SensitiveErrorMail
from couchforms.exceptions import UnexpectedDeletedXForm
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX, is_deleted
from dimagi.utils.logging import notify_exception
from soil import DownloadBase

from casexml.apps.case.xform import get_case_ids_from_form
from couchforms.models import XFormInstance

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
def tag_cases_as_deleted_and_remove_indices(cls, docs, deletion_id):
    for doc in docs:
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
    cls.get_db().bulk_save(docs)


@task(rate_limit=2, queue='background_queue', ignore_result=True, acks_late=True)
def tag_forms_as_deleted_rebuild_associated_cases(form_id_list, deletion_id,
                                                  deleted_cases=None):
    """
    Upon user deletion, mark associated forms as deleted and prep cases
    for a rebuild.
    - 2 saves/sec for cloudant slowness (rate_limit)
    """
    if deleted_cases is None:
        deleted_cases = set()

    cases_to_rebuild = set()
    forms_to_check = get_docs(XFormInstance.get_db(), form_id_list)
    forms_to_save = []
    for form in forms_to_check:
        if not is_deleted(form):
            form['doc_type'] += DELETED_SUFFIX
            form['-deletion_id'] = deletion_id
            forms_to_save.append(form)

        # rebuild all cases anyways since we don't know if this has run or not if the task was killed
        cases_to_rebuild.update(get_case_ids_from_form(form))

    XFormInstance.get_db().bulk_save(forms_to_save)
    for case in cases_to_rebuild - deleted_cases:
        _rebuild_case_with_retries.delay(case)


@task(bind=True, queue='background_queue', ignore_result=True,
      default_retry_delay=5 * 60, max_retries=3, acks_late=True)
def _rebuild_case_with_retries(self, case_id):
    """
    Rebuild a case with retries
    - retry in 5 min if failure occurs after (default_retry_delay)
    - retry a total of 3 times
    """
    from casexml.apps.case.cleanup import rebuild_case
    try:
        rebuild_case(case_id)
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
    from corehq.apps.users.models import DomainInvitation
    days_to_resend = (15, 29)
    days_to_expire = 30
    domains = Domain.get_all()
    for domain in domains:
        invitations = DomainInvitation.by_domain(domain.name)
        for invitation in invitations:
            days = (datetime.utcnow() - invitation.invited_on).days
            if days in days_to_resend:
                invitation.send_activation_email(days_to_expire - days)
