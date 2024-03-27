from datetime import datetime, timedelta
from typing import List, Optional

from django.conf import settings
from django.utils.translation import gettext as _

from couchdbkit import ResourceNotFound

from dimagi.utils.logging import notify_error, notify_exception
from soil import DownloadBase

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.form_processor.models import CommCareCase, XFormInstance


def add_cases_to_case_group(domain, case_group_id, uploaded_data, progress_tracker):
    from corehq.apps.hqcase.utils import get_case_by_identifier

    response = {
        'errors': [],
        'success': [],
    }
    try:
        case_group = CommCareCaseGroup.get(case_group_id)
    except ResourceNotFound:
        response['errors'].append(_("The case group was not found."))
        return response

    num_rows = len(uploaded_data)
    progress_tracker(0, num_rows)
    for row_number, row in enumerate(uploaded_data):
        identifier = row.get('case_identifier')
        case = None
        if identifier is not None:
            case = get_case_by_identifier(domain, str(identifier))
        if not case:
            response['errors'].append(
                _("Could not find case with identifier '{}'.").format(identifier)
            )
        elif case.doc_type != 'CommCareCase':
            response['errors'].append(
                _("It looks like the case with identifier '{}' "
                  "is marked as deleted.").format(identifier)
            )
        elif case.case_id in case_group.cases:
            response['errors'].append(
                _("A case with identifier '{}' already exists in this "
                  "group.").format(identifier)
            )
        else:
            case_group.cases.append(case.case_id)
            response['success'].append(
                _("Case with identifier '{}' has been added to this "
                  "group.").format(identifier)
            )
        progress_tracker(row_number + 1, num_rows)

    if response['success']:
        case_group.save()

    return response


def archive_or_restore_forms(domain, user_id, username, form_ids, archive_or_restore, task=None, from_excel=False):
    response = {
        'errors': [],
        'success': [],
    }

    missing_forms = set(form_ids)
    success_count = 0

    if task:
        DownloadBase.set_progress(task, 0, len(form_ids))

    for xform in XFormInstance.objects.iter_forms(form_ids, domain):
        missing_forms.discard(xform.form_id)

        if xform.domain != domain:
            response['errors'].append(_("XForm {form_id} does not belong to domain {domain}").format(
                form_id=xform.form_id, domain=domain))
            continue

        xform_string = _("XForm {form_id} for domain {domain} by user '{username}'").format(
            form_id=xform.form_id,
            domain=xform.domain,
            username=username)

        try:
            if archive_or_restore.is_archive_mode():
                xform.archive(user_id=user_id)
                message = _("Successfully archived {form}").format(form=xform_string)
            else:
                xform.unarchive(user_id=user_id)
                message = _("Successfully unarchived {form}").format(form=xform_string)
            response['success'].append(message)
            success_count = success_count + 1
        except Exception as e:
            response['errors'].append(_("Could not archive {form}: {error}").format(
                form=xform_string, error=e))

        if task:
            DownloadBase.set_progress(task, success_count, len(form_ids))

    for missing_form_id in missing_forms:
        response['errors'].append(
            _("Could not find XForm {form_id}").format(form_id=missing_form_id))

    if from_excel:
        return response

    response["success_count_msg"] = _("{success_msg} {count} form(s)".format(
        success_msg=archive_or_restore.success_text,
        count=success_count))
    return {"messages": response}


def property_references_parent(case_property):
    return isinstance(case_property, str) and (
        case_property.startswith("parent/")
        or case_property.startswith("host/")
    )


def operate_on_payloads(
    repeat_record_ids: List,
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    task: Optional = None,
    from_excel: bool = False,
):
    if not repeat_record_ids:
        return {'messages': {'errors': [_('No payloads specified')]}}

    response = {
        'errors': [],
        'success': [],
    }

    success_count = 0

    if task:
        DownloadBase.set_progress(task, 0, len(repeat_record_ids))

    for record_id in repeat_record_ids:
        record = _get_sql_repeat_record(domain, record_id)

        if record:
            try:
                if action == 'resend':
                    record.fire(force_send=True)
                    message = _("Successfully resent repeat record (id={})").format(record_id)
                elif action == 'cancel':
                    record.cancel()
                    record.save()
                    message = _("Successfully cancelled repeat record (id={})").format(record_id)
                elif action == 'requeue':
                    record.requeue()
                    message = _("Successfully requeued repeat record (id={})").format(record_id)
                else:
                    raise ValueError(f'Unknown action {action!r}')
                response['success'].append(message)
                success_count = success_count + 1
            except Exception as e:
                message = _("Could not perform action for repeat record (id={}): {}").format(record_id, e)
                response['errors'].append(message)

            if task:
                DownloadBase.set_progress(task, success_count, len(repeat_record_ids))

    if from_excel:
        return response

    if success_count:
        response["success_count_msg"] = _(
            "Successfully performed {action} action on {count} form(s)"
        ).format(action=action, count=success_count)
    else:
        response["success_count_msg"] = ''

    return {"messages": response}


def _get_sql_repeat_record(domain, record_id):
    from corehq.motech.repeaters.models import SQLRepeatRecord, is_sql_id

    where = {"id": record_id} if is_sql_id(record_id) else {"couch_id": record_id}
    try:
        return SQLRepeatRecord.objects.get(domain=domain, **where)
    except SQLRepeatRecord.DoesNotExist:
        return None


def iter_cases_and_run_rules(domain, case_iterator, rules, now, run_id, case_type, db=None, progress_helper=None):
    from corehq.apps.data_interfaces.models import (
        CaseRuleActionResult,
        DomainCaseRuleRun,
    )
    HALT_AFTER = 23 * 60 * 60

    domain_obj = Domain.get_by_name(domain)
    max_allowed_updates = domain_obj.auto_case_update_limit or settings.MAX_RULE_UPDATES_IN_ONE_RUN
    start_run = datetime.utcnow()
    case_update_result = CaseRuleActionResult()

    cases_checked = 0
    last_migration_check_time = None

    for case in case_iterator:
        migration_in_progress, last_migration_check_time = _check_data_migration_in_progress(
            domain, last_migration_check_time
        )

        time_elapsed = datetime.utcnow() - start_run
        if (
            time_elapsed.seconds > HALT_AFTER or case_update_result.total_updates >= max_allowed_updates
            or migration_in_progress
        ):
            notify_error("Halting rule run for domain %s and case type %s." % (domain, case_type))

            return DomainCaseRuleRun.done(
                run_id, cases_checked, case_update_result, db=db, halted=True
            )

        case_update_result.add_result(run_rules_for_case(case, rules, now))
        if progress_helper is not None:
            progress_helper.increment_current_case_count()
        cases_checked += 1
    return DomainCaseRuleRun.done(run_id, cases_checked, case_update_result, db=db)


def _check_data_migration_in_progress(domain, last_migration_check_time):
    utcnow = datetime.utcnow()
    if last_migration_check_time is None or (utcnow - last_migration_check_time) > timedelta(minutes=1):
        return any_migrations_in_progress(domain), utcnow

    return False, last_migration_check_time


def run_rules_for_case(case, rules, now):
    from corehq.apps.data_interfaces.models import CaseRuleActionResult
    aggregated_result = CaseRuleActionResult()
    last_result = None
    for rule in rules:
        if last_result:
            if (
                last_result.num_updates > 0 or last_result.num_related_updates > 0
                or last_result.num_related_closes > 0
            ):
                case = CommCareCase.objects.get_case(case.case_id, case.domain)

        try:
            last_result = rule.run_rule(case, now)
        except Exception:
            last_result = CaseRuleActionResult(num_errors=1)
            notify_exception(None, "Error applying case update rule", {
                'domain': case.domain,
                'rule_pk': rule.pk,
                'case_id': case.case_id,
            })

        aggregated_result.add_result(last_result)
        if last_result.num_closes > 0:
            break

    return aggregated_result
