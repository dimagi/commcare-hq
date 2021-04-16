from typing import List, Optional

from django.utils.translation import ugettext as _

from couchdbkit import ResourceNotFound

from soil import DownloadBase

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.repeaters.const import RECORD_CANCELLED_STATE


def add_cases_to_case_group(domain, case_group_id, uploaded_data, progress_tracker):
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

    for xform in FormAccessors(domain).iter_forms(form_ids):
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
        case_property.startswith("parent/") or
        case_property.startswith("host/")
    )


def operate_on_payloads(
    repeat_record_ids: List[str],
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool,
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
        if use_sql:
            record = _get_sql_repeat_record(domain, record_id)
        else:
            record = _get_couch_repeat_record(domain, record_id)

        if record:
            try:
                if action == 'resend':
                    record.fire(force_send=True)
                    message = _("Successfully resent repeat record (id={})").format(record_id)
                elif action == 'cancel':
                    if use_sql:
                        record.state = RECORD_CANCELLED_STATE
                    else:
                        record.cancel()
                    record.save()
                    message = _("Successfully cancelled repeat record (id={})").format(record_id)
                elif action == 'requeue':
                    record.requeue()
                    if not use_sql:
                        record.save()
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


def _get_couch_repeat_record(domain, record_id):
    from corehq.motech.repeaters.models import RepeatRecord

    try:
        couch_record = RepeatRecord.get(record_id)
    except ResourceNotFound:
        return None
    if couch_record.domain != domain:
        return None
    return couch_record


def _get_sql_repeat_record(domain, record_id):
    from corehq.motech.repeaters.models import SQLRepeatRecord

    try:
        return SQLRepeatRecord.objects.get(domain=domain, pk=record_id)
    except SQLRepeatRecord.DoesNotExist:
        return None
