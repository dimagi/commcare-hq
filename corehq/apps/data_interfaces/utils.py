from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCaseGroup
from corehq.apps.hqcase.utils import get_case_by_identifier
from django.utils.translation import ugettext as _
from couchforms.models import XFormInstance


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
        elif case._id in case_group.cases:
            response['errors'].append(_("A case with identifier %s already exists in this group." % identifier))
        else:
            case_group.cases.append(case._id)
            response['success'].append(_("Case with identifier '%s' has been added to this group." % identifier))

    if response['success']:
        case_group.save()

    return response


def archive_forms(user, uploaded_data):
    response = {
        'errors': [],
        'success': [],
    }

    for row in uploaded_data:
        xform_id = row.get('form_id')
        try:
            xform = XFormInstance.get(xform_id)
        except Exception as e:
            response['errors'].append(
                _(u"Could not get XFormInstance {form_id}: {error}").format(form_id=xform_id, error=e))
            continue

        xform_string = _(u"XFORM {form_id} for domain {domain} by user '{username}'").format(
            form_id=xform['_id'],
            domain=xform['domain'],
            username=user.username)

        try:
            xform.archive(user=user.username)
            response['success'].append(_(u"Successfully archived {form}").format(form=xform_string))
        except Exception as e:
            response['errors'].append(_(u"Could not archive {form}: {error}").format(
                form=xform_string, error=e))

    return response
