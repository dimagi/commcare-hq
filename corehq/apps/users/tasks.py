from datetime import datetime
from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task
from celery.utils.log import get_task_logger
from corehq.util.log import SensitiveErrorMail
from couchforms.exceptions import UnexpectedDeletedXForm
import settings
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.undo import DELETED_SUFFIX
from django.core.cache import cache
import uuid
from soil import CachedDownload, DownloadBase

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
def tag_docs_as_deleted(cls, docs, deletion_id):
    for doc in docs:
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
    cls.get_db().bulk_save(docs)


@task(bind=True, rate_limit=2, queue='background_queue', ignore_result=True,
      default_retry_delay=5 * 60, max_retries=3)
def tag_forms_as_deleted_rebuild_associated_cases(self, formlist, deletion_id,
                                                  deleted_cases=None):
    """ Upon user deletion, mark associated forms as deleted and prep cases
    for a rebuild.
    - 2 saves/sec for cloudant slowness (rate_limit)
    - retry in 5 min if failure occurs after (default_retry_delay)
    - retry a total of 3 times
    """
    from casexml.apps.case.cleanup import rebuild_case
    if deleted_cases is None:
        deleted_cases = set()

    cases_to_rebuild = set()
    for form in formlist:
        form['doc_type'] += DELETED_SUFFIX
        form['-deletion_id'] = deletion_id
        cases_to_rebuild.update(get_case_ids_from_form(form))
    XFormInstance.get_db().bulk_save(formlist)

    try:
        for case in cases_to_rebuild - deleted_cases:
            rebuild_case(case)
    except UnexpectedDeletedXForm as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Maximum Retries Exceeded for tag_forms_as_deleted. "
                         "Deleted XForms found preventing cases from being "
                         "rebuilt.")

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
