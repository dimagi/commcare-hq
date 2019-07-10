from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
from couchdbkit import ResourceNotFound
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.form_processor.interfaces.dbaccessors import FormAccessors

from soil import DownloadBase
import six


def add_cases_to_case_group(domain, case_group_id, uploaded_data):
    response = {
        'errors': [],
        'success': [],
    }
    try:
        case_group = CommCareCaseGroup.get(case_group_id)
    except ResourceNotFound:
        response['errors'].append(_("The case group was not found."))
        return response

    for row in uploaded_data:
        identifier = row.get('case_identifier')
        case = None
        if identifier is not None:
            case = get_case_by_identifier(domain, str(identifier))
        if not case:
            response['errors'].append(_("Could not find case with identifier '%s'." % identifier))
        elif case.doc_type != 'CommCareCase':
            response['errors'].append(_("It looks like the case with identifier '%s' is deleted" % identifier))
        elif case.case_id in case_group.cases:
            response['errors'].append(_("A case with identifier %s already exists in this group." % identifier))
        else:
            case_group.cases.append(case.case_id)
            response['success'].append(_("Case with identifier '%s' has been added to this group." % identifier))

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
    return isinstance(case_property, six.string_types) and (
        case_property.startswith("parent/") or
        case_property.startswith("host/")
    )
