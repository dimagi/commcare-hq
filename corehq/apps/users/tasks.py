from datetime import datetime
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from couchdbkit import BulkSaveError, ResourceConflict

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import get_case_ids_from_form
from couchforms.exceptions import UnexpectedDeletedXForm
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.couch.bulk import BulkFetchException
from dimagi.utils.logging import notify_exception
from dimagi.utils.retry import retry_on
from soil import DownloadBase

from corehq import toggles
from corehq.apps.celery import periodic_task, task
from corehq.apps.domain.models import Domain
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import (
    CommCareCase,
    CommCareCaseIndex,
    UserArchivedRebuild,
    XFormInstance,
)
from corehq.util.celery_utils import (
    deserialize_run_every_setting,
    run_periodic_task_again,
)
from corehq.util.metrics import metrics_counter

logger = get_task_logger(__name__)


@task(serializer='pickle')
def bulk_download_usernames_async(domain, download_id, user_filters, owner_id):
    from corehq.apps.users.bulk_download import dump_usernames
    dump_usernames(domain, download_id, user_filters, bulk_download_usernames_async, owner_id)


@task(serializer='pickle')
def bulk_download_users_async(domain, download_id, user_filters, is_web_download, owner_id):
    from corehq.apps.users.bulk_download import (
        GroupNameError,
        dump_users_and_groups,
        dump_web_users,
    )
    errors = []
    try:
        args = [domain, download_id, user_filters, bulk_download_users_async, owner_id]
        if is_web_download:
            dump_web_users(*args)
        else:
            dump_users_and_groups(*args)
    except GroupNameError as e:
        group_urls = [
            reverse('group_members', args=[domain, group.get_id])
            for group in e.blank_groups
        ]

        def make_link(url, i):
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                _('Blank Group %s') % i
            )

        group_links = [
            make_link(url, i + 1)
            for i, url in enumerate(group_urls)
        ]
        errors.append(format_html(
            _(
                'The following groups have no name. '
                'Please name them before continuing: {}'
            ),
            mark_safe(', '.join(group_links))  # nosec: no user input
        ))
    except BulkFetchException:
        errors.append(_('Error exporting data. Please try again later.'))

    return {
        'errors': errors
    }


# rate limit to two bulk saves per second so cloudant has time to reindex
@task(serializer='pickle', rate_limit=2, queue='background_queue', ignore_result=True)
def tag_cases_as_deleted_and_remove_indices(domain, case_ids, deletion_id, deletion_date=None):
    if not deletion_date:
        deletion_date = datetime.utcnow()
    from corehq.apps.data_interfaces.tasks import delete_duplicates_for_cases
    from corehq.apps.sms.tasks import delete_phone_numbers_for_owners
    from corehq.messaging.scheduling.tasks import (
        delete_schedule_instances_for_cases,
    )
    CommCareCase.objects.soft_delete_cases(domain, list(case_ids), deletion_date, deletion_id)
    _remove_indices_from_deleted_cases_task.delay(domain, case_ids)
    delete_phone_numbers_for_owners.delay(case_ids)
    delete_schedule_instances_for_cases.delay(domain, case_ids)
    delete_duplicates_for_cases.delay(case_ids)


@task(serializer='pickle', rate_limit=2, queue='background_queue', ignore_result=True, acks_late=True)
def tag_forms_as_deleted_rebuild_associated_cases(user_id, domain, form_id_list, deletion_id,
                                                  deletion_date, deleted_cases=None):
    """
    Upon user deletion, mark associated forms as deleted and prep cases
    for a rebuild.
    - 2 saves/sec for cloudant slowness (rate_limit)
    """
    deleted_cases = deleted_cases or set()
    cases_to_rebuild = set()

    for form in XFormInstance.objects.iter_forms(form_id_list, domain):
        if form.domain != domain or not form.is_normal:
            continue

        # rebuild all cases anyways since we don't know if this has run or not if the task was killed
        cases_to_rebuild.update(get_case_ids_from_form(form))

    # do this after getting case_id's since iter_forms won't return deleted forms
    XFormInstance.objects.soft_delete_forms(domain, list(form_id_list), deletion_date, deletion_id)

    detail = UserArchivedRebuild(user_id=user_id)
    for case_id in cases_to_rebuild - deleted_cases:
        _rebuild_case_with_retries.delay(domain, case_id, detail)


def _get_forms_to_modify(domain, modified_forms, modified_cases, is_deletion):
    """Used on user.retire() and user.unretire()

    Returns a list of IDs of forms which only modify the cases passed in and
    which aren't already listed in `modified_forms`.
    """
    form_ids_to_modify = set()
    for case_id in modified_cases:
        try:
            xform_ids = CommCareCase.objects.get_case(case_id, domain).xform_ids
        except CaseNotFound:
            xform_ids = []
        form_ids_to_modify |= set(xform_ids) - modified_forms

    def _is_safe_to_modify(form):
        if form.domain != domain:
            return False

        case_ids = get_case_ids_from_form(form)
        # all cases touched by the form and not already modified
        for case in CommCareCase.objects.iter_cases(case_ids - modified_cases):
            if case.is_deleted != is_deletion:
                # we can't delete/undelete this form - this would change the state of `case`
                return False

        # all cases touched by this form are deleted
        return True

    all_forms = XFormInstance.objects.iter_forms(form_ids_to_modify, domain)
    return [form.form_id for form in all_forms if _is_safe_to_modify(form)]


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def tag_system_forms_as_deleted(domain, deleted_forms, deleted_cases, deletion_id, deletion_date):
    to_delete = _get_forms_to_modify(domain, deleted_forms, deleted_cases, is_deletion=True)
    XFormInstance.objects.soft_delete_forms(domain, to_delete, deletion_date, deletion_id)


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def undelete_system_forms(domain, deleted_forms, deleted_cases):
    """The reverse of tag_system_forms_as_deleted; called on user.unretire()"""
    to_undelete = _get_forms_to_modify(domain, deleted_forms, deleted_cases, is_deletion=False)
    XFormInstance.objects.soft_undelete_forms(domain, to_undelete)


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def _remove_indices_from_deleted_cases_task(domain, case_ids):
    if toggles.SKIP_REMOVE_INDICES.enabled(domain):
        return

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
    indexes_referencing_deleted_cases = \
        CommCareCaseIndex.objects.get_all_reverse_indices_info(domain, list(case_ids))
    case_updates = [
        CaseBlock(
            case_id=index_info.case_id,
            index={
                index_info.identifier: (index_info.referenced_type, '')  # blank string = delete index
            }
        ).as_text()
        for index_info in indexes_referencing_deleted_cases
        if index_info.case_id not in deleted_ids
    ]
    device_id = __name__ + ".remove_indices_from_deleted_cases"
    submit_case_blocks(case_updates, domain, device_id=device_id)


@task(serializer='pickle', bind=True, queue='background_queue', ignore_result=True,
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
                None,
                f"Maximum Retries Exceeded while rebuilding case {case_id} during deletion.",
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
    for domain_obj in domains:
        invitations = Invitation.by_domain(domain_obj.name)
        for invitation in invitations:
            days = (datetime.utcnow() - invitation.invited_on).days
            if days in days_to_resend:
                invitation.send_activation_email(days_to_expire - days)


@task(serializer='pickle')
def turn_on_demo_mode_task(commcare_user_id, domain):
    from corehq.apps.ota.utils import turn_on_demo_mode
    from corehq.apps.users.models import CommCareUser

    user = CommCareUser.get(commcare_user_id)
    DownloadBase.set_progress(turn_on_demo_mode_task, 0, 100)
    results = turn_on_demo_mode(user, domain)
    DownloadBase.set_progress(turn_on_demo_mode_task, 100, 100)

    return {
        'messages': results
    }


@task(serializer='pickle')
def reset_demo_user_restore_task(commcare_user_id, domain):
    from corehq.apps.ota.utils import reset_demo_user_restore
    from corehq.apps.users.models import CommCareUser

    user = CommCareUser.get(commcare_user_id)

    DownloadBase.set_progress(reset_demo_user_restore_task, 0, 100)

    try:
        reset_demo_user_restore(user, domain)
        results = {'errors': []}
    except Exception as e:
        notify_exception(None, message=str(e))
        results = {'errors': [
            _("Something went wrong in creating restore for the user. Please try again or report an issue")
        ]}

    DownloadBase.set_progress(reset_demo_user_restore_task, 100, 100)
    return {'messages': results}


@task(serializer='pickle')
def remove_unused_custom_fields_from_users_task(domain):
    """Removes all unused custom data fields from all users in the domain"""
    from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
    from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
    from corehq.apps.users.views.mobile.custom_data_fields import (
        CUSTOM_USER_DATA_FIELD_TYPE,
    )
    fields_definition = CustomDataFieldsDefinition.get(domain, CUSTOM_USER_DATA_FIELD_TYPE)
    assert fields_definition, 'remove_unused_custom_fields_from_users_task called without a valid definition'
    schema_fields = {f.slug for f in fields_definition.get_fields()}
    for user in get_all_commcare_users_by_domain(domain):
        user_data = user.get_user_data(domain)
        changed = user_data.remove_unrecognized(schema_fields)
        if changed:
            user.save()


@task()
def update_domain_date(user_id, domain):
    from corehq.apps.users.models import WebUser
    user = WebUser.get_by_user_id(user_id)
    domain_membership = user.get_domain_membership(domain, allow_enterprise=False)
    today = datetime.today().date()
    if domain_membership and (
            not domain_membership.last_accessed or domain_membership.last_accessed < today):
        domain_membership.last_accessed = today
        try:
            user.save()
        except ResourceConflict:
            pass


process_reporting_metadata_staging_schedule = deserialize_run_every_setting(
    settings.USER_REPORTING_METADATA_BATCH_SCHEDULE
)


@periodic_task(
    run_every=process_reporting_metadata_staging_schedule,
    queue='background_queue',
)
def process_reporting_metadata_staging():
    from corehq.apps.users.models import UserReportingMetadataStaging

    lock_key = "PROCESS_REPORTING_METADATA_STAGING_TASK"
    process_reporting_metadata_lock = get_redis_lock(
        lock_key,
        timeout=60 * 60,  # one hour
        name=lock_key,
    )
    if not process_reporting_metadata_lock.acquire(blocking=False):
        metrics_counter("commcare.process_reporting_metadata.locked_out")
        return

    try:
        start = datetime.utcnow()
        _process_reporting_metadata_staging()
    finally:
        process_reporting_metadata_lock.release()

    duration = datetime.utcnow() - start
    run_again = run_periodic_task_again(process_reporting_metadata_staging_schedule, start, duration)
    if run_again and UserReportingMetadataStaging.objects.exists():
        process_reporting_metadata_staging.delay()


def _process_reporting_metadata_staging():
    from corehq.apps.users.models import UserReportingMetadataStaging
    for i in range(100):
        with transaction.atomic():
            records = (UserReportingMetadataStaging.objects.select_for_update(skip_locked=True).order_by('pk'))[:1]
            for record in records:
                _process_record_with_retry(record)
                record.delete()


@retry_on(ResourceConflict, delays=[0, 0.5])
def _process_record_with_retry(record):
    """
    It is possible that an unrelated user update is saved to the db while we are processing the record
    but before saving any user updates resulting from process_record. In this case, a ResourceConflict is
    raised so we should try once more to see if it was just bad timing or a persistent error.
    """
    from corehq.apps.users.models import CouchUser
    user = CouchUser.get_by_user_id(record.user_id, record.domain)
    record.process_record(user)


@task(queue='background_queue', acks_late=True)
def apply_correct_demo_mode_to_loadtest_user(commcare_user_id):
    """
    If ``loadtest_factor`` is set on a non-demo user, then that user
    will become a demo user for as long as ``loadtest_factor`` > 1.

    If ``loadtest_factor`` is set on a user that is already a demo
    user, their status as a demo user is not affected.

    ``is_loadtest_user`` is used for determining when to set or reset
    their status as a demo user.
    """
    from corehq.apps.ota.utils import turn_off_demo_mode, turn_on_demo_mode
    from corehq.apps.users.models import CommCareUser

    user = CommCareUser.get_by_user_id(commcare_user_id)
    if user.loadtest_factor and user.loadtest_factor > 1:
        if not user.is_demo_user:
            user.is_loadtest_user = True  # This change gets saved by
            # turn_on_demo_mode() > reset_demo_user_restore()
            turn_on_demo_mode(user, user.domain)
    else:
        if user.is_loadtest_user:
            user.is_loadtest_user = False  # This change gets saved by
            # turn_off_demo_mode()
            turn_off_demo_mode(user)


@task(queue='background_queue')
def remove_users_test_cases(domain, owner_ids):
    from corehq.apps.reports.util import domain_copied_cases_by_owner

    test_case_ids = domain_copied_cases_by_owner(domain, owner_ids)
    tag_cases_as_deleted_and_remove_indices(domain, test_case_ids, uuid4().hex)
