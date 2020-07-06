from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task
from celery.utils.log import get_task_logger
from couchdbkit import BulkSaveError, ResourceConflict

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import get_case_ids_from_form
from corehq.util.metrics import metrics_gauge
from corehq.util.metrics.const import MPM_MAX
from couchforms.exceptions import UnexpectedDeletedXForm
from dimagi.utils.couch.bulk import BulkFetchException
from dimagi.utils.logging import notify_exception
from soil import DownloadBase

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.user_importer.tasks import import_users_and_groups
from corehq.form_processor.exceptions import CaseNotFound, NotAllowed
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.models import UserArchivedRebuild
from corehq.util.celery_utils import deserialize_run_every_setting, run_periodic_task_again

logger = get_task_logger(__name__)


@task(serializer='pickle')
def bulk_download_usernames_async(domain, download_id, user_filters):
    from corehq.apps.users.bulk_download import dump_usernames
    dump_usernames(domain, download_id, user_filters, bulk_download_usernames_async)


@task(serializer='pickle')
def bulk_download_users_async(domain, download_id, user_filters):
    from corehq.apps.users.bulk_download import dump_users_and_groups, GroupNameError
    errors = []
    try:
        dump_users_and_groups(
            domain,
            download_id,
            user_filters,
            bulk_download_users_async,
        )
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
            mark_safe(', '.join(group_links))
        ))
    except BulkFetchException:
        errors.append(_('Error exporting data. Please try again later.'))

    return {
        'errors': errors
    }


@task(serializer='pickle', rate_limit=2, queue='background_queue', ignore_result=True)  # limit this to two bulk saves a second so cloudant has time to reindex
def tag_cases_as_deleted_and_remove_indices(domain, case_ids, deletion_id, deletion_date):
    from corehq.apps.sms.tasks import delete_phone_numbers_for_owners
    from corehq.messaging.scheduling.tasks import delete_schedule_instances_for_cases
    NotAllowed.check(domain)
    CaseAccessors(domain).soft_delete_cases(list(case_ids), deletion_date, deletion_id)
    _remove_indices_from_deleted_cases_task.delay(domain, case_ids)
    delete_phone_numbers_for_owners.delay(case_ids)
    delete_schedule_instances_for_cases.delay(domain, case_ids)


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

    for form in FormAccessors(domain).iter_forms(form_id_list):
        if form.domain != domain or not form.is_normal:
            continue

        # rebuild all cases anyways since we don't know if this has run or not if the task was killed
        cases_to_rebuild.update(get_case_ids_from_form(form))

    # do this after getting case_id's since iter_forms won't return deleted forms
    FormAccessors(domain).soft_delete_forms(list(form_id_list), deletion_date, deletion_id)

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
            xform_ids = CaseAccessors(domain).get_case(case_id).xform_ids
        except CaseNotFound:
            xform_ids = []
        form_ids_to_modify |= set(xform_ids) - modified_forms

    def _is_safe_to_modify(form):
        if form.domain != domain:
            return False

        case_ids = get_case_ids_from_form(form)
        # all cases touched by the form and not already modified
        for case in CaseAccessors(domain).iter_cases(case_ids - modified_cases):
            if case.is_deleted != is_deletion:
                # we can't delete/undelete this form - this would change the state of `case`
                return False

        # all cases touched by this form are deleted
        return True

    if is_deletion or Domain.get_by_name(domain).use_sql_backend:
        all_forms = FormAccessors(domain).iter_forms(form_ids_to_modify)
    else:
        # accessor.iter_forms doesn't include deleted forms on the couch backend
        all_forms = list(map(FormAccessors(domain).get_form, form_ids_to_modify))
    return [form.form_id for form in all_forms if _is_safe_to_modify(form)]


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def tag_system_forms_as_deleted(domain, deleted_forms, deleted_cases, deletion_id, deletion_date):
    to_delete = _get_forms_to_modify(domain, deleted_forms, deleted_cases, is_deletion=True)
    FormAccessors(domain).soft_delete_forms(to_delete, deletion_date, deletion_id)


@task(serializer='pickle', queue='background_queue', ignore_result=True, acks_late=True)
def undelete_system_forms(domain, deleted_forms, deleted_cases):
    """The reverse of tag_system_forms_as_deleted; called on user.unretire()"""
    to_undelete = _get_forms_to_modify(domain, deleted_forms, deleted_cases, is_deletion=False)
    FormAccessors(domain).soft_undelete_forms(to_undelete)


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
    indexes_referencing_deleted_cases = CaseAccessors(domain).get_all_reverse_indices_info(list(case_ids))
    case_updates = [
        CaseBlock.deprecated_init(
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
    from corehq.apps.users.custom_data import remove_unused_custom_fields_from_users
    remove_unused_custom_fields_from_users(domain)


@task()
def update_domain_date(user_id, domain):
    from corehq.apps.users.models import WebUser
    user = WebUser.get_by_user_id(user_id)
    domain_membership = user.get_domain_membership(domain, allow_mirroring=False)
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
    from corehq.apps.users.models import (
        CouchUser, UserReportingMetadataStaging
    )

    start = datetime.utcnow()

    with transaction.atomic():
        records = (
            UserReportingMetadataStaging.objects.select_for_update(skip_locked=True).order_by('pk')
        )[:100]
        for record in records:
            user = CouchUser.get_by_user_id(record.user_id, record.domain)
            try:
                record.process_record(user)
            except ResourceConflict:
                # https://sentry.io/organizations/dimagi/issues/1479516073/
                user = CouchUser.get_by_user_id(record.user_id, record.domain)
                record.process_record(user)
            record.delete()

    duration = datetime.utcnow() - start
    run_again = run_periodic_task_again(process_reporting_metadata_staging_schedule, start, duration)
    if run_again and UserReportingMetadataStaging.objects.exists():
        process_reporting_metadata_staging.delay()


@periodic_task(run_every=crontab(minute='*/10'), queue='background_queue')
def gauge_pending_user_confirmations():
    metric_name = 'commcare.pending_user_confirmations'
    from corehq.apps.users.models import Invitation
    for stats in (Invitation.objects.filter(is_accepted=False).all()
                  .values('domain').annotate(Count('domain'))):
        metrics_gauge(
            metric_name, stats['domain__count'], tags={
                'domain': stats['domain'],
                'user_type': 'web',
            },
            multiprocess_mode=MPM_MAX
        )

    from corehq.apps.users.analytics import get_inactive_commcare_users_in_domain
    for doc in Domain.get_all(include_docs=False):
        domain_name = doc['key']
        users = get_inactive_commcare_users_in_domain(domain_name)
        num_unconfirmed = sum(1 for u in users if not u.is_account_confirmed)
        if num_unconfirmed:
            metrics_gauge(
                metric_name, num_unconfirmed, tags={
                    'domain': domain_name,
                    'user_type': 'mobile',
                },
                multiprocess_mode=MPM_MAX
            )
