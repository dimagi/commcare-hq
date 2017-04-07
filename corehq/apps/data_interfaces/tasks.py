from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.utils.log import get_task_logger
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, AUTO_UPDATE_XMLNS
from corehq.util.decorators import serial_task
from datetime import datetime

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.utils import add_cases_to_case_group, archive_forms_old, archive_or_restore_forms
from corehq.toggles import DATA_MIGRATION
from .interfaces import FormManagementMode, BulkFormManagementInterface
from .dispatcher import EditDataInterfaceDispatcher
from corehq.util.log import send_HTML_email
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_error


logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60
HALT_AFTER = 23 * 60 * 60


@task(ignore_result=True)
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    cache.set(download_id, results, ONE_HOUR)


@task(ignore_result=True)
def bulk_archive_forms(domain, couch_user, uploaded_data):
    # archive using Excel-data
    response = archive_forms_old(domain, couch_user.user_id, couch_user.username, uploaded_data)

    for msg in response['success']:
        logger.info("[Data interfaces] %s", msg)
    for msg in response['errors']:
        logger.info("[Data interfaces] %s", msg)

    html_content = render_to_string('data_interfaces/archive_email.html', response)
    send_HTML_email(_('Your archived forms'), couch_user.email, html_content)


@task
def bulk_form_management_async(archive_or_restore, domain, couch_user, form_ids):
    task = bulk_form_management_async
    mode = FormManagementMode(archive_or_restore, validate=True)

    if not form_ids:
        return {'messages': {'errors': [_('No Forms are supplied')]}}

    response = archive_or_restore_forms(domain, couch_user.user_id, couch_user.username, form_ids, mode, task)
    return response


@periodic_task(
    run_every=crontab(hour=0, minute=0),
    queue=settings.CELERY_PERIODIC_QUEUE,
    ignore_result=True
)
def run_case_update_rules(now=None):
    domains = (AutomaticUpdateRule
               .objects
               .filter(active=True, deleted=False)
               .values_list('domain', flat=True)
               .distinct()
               .order_by('domain'))
    for domain in domains:
        if not DATA_MIGRATION.enabled(domain):
            run_case_update_rules_for_domain.delay(domain, now)


@serial_task(
    '{domain}',
    timeout=36 * 60 * 60,
    max_retries=0,
    queue='background_queue',
)
def run_case_update_rules_for_domain(domain, now=None):
    now = now or datetime.utcnow()
    start_run = datetime.utcnow()
    all_rules = AutomaticUpdateRule.by_domain(domain)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(all_rules)

    for case_type, rules in rules_by_case_type.iteritems():
        boundary_date = AutomaticUpdateRule.get_boundary_date(rules, now)
        case_id_chunks = AutomaticUpdateRule.get_case_ids(domain, case_type, boundary_date)

        for case_ids in case_id_chunks:
            for case in CaseAccessors(domain).iter_cases(case_ids):
                time_elapsed = datetime.utcnow() - start_run
                if time_elapsed.seconds > HALT_AFTER:
                    notify_error(
                        "Halting rule run for domain %s as it's been running for more than a day." % domain
                    )
                    return

                for rule in rules:
                    stop_processing = rule.apply_rule(case, now)
                    if stop_processing:
                        break

        for rule in rules:
            rule.last_run = now
            rule.save()


@task(queue='background_queue', acks_late=True, ignore_result=True)
def run_case_update_rules_on_save(case):
    key = 'case-update-on-save-case-{case}'.format(case=case.case_id)
    with CriticalSection([key]):
        update_case = True
        if case.xform_ids:
            last_form = FormAccessors(case.domain).get_form(case.xform_ids[-1])
            update_case = last_form.xmlns != AUTO_UPDATE_XMLNS
        if update_case:
            rules = AutomaticUpdateRule.by_domain(case.domain).filter(case_type=case.type)
            now = datetime.utcnow()
            for rule in rules:
                stop_processing = rule.apply_rule(case, now)
                if stop_processing:
                    break
