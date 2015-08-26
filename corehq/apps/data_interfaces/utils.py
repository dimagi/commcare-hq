from django.utils.translation import ugettext as _
from couchdbkit import ResourceNotFound
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqcase.utils import get_case_by_identifier
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


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


def archive_forms(domain, user, uploaded_data):
    response = {
        'errors': [],
        'success': [],
    }

    form_ids = [row.get('form_id') for row in uploaded_data]
    missing_forms = set(form_ids)

    for xform_doc in iter_docs(XFormInstance.get_db(), form_ids):
        xform = XFormInstance.wrap(xform_doc)
        missing_forms.discard(xform['_id'])

        if xform['domain'] != domain:
            response['errors'].append(_(u"XFORM {form_id} does not belong to domain {domain}").format(
                form_id=xform['_id'], domain=xform['domain']))
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

    for missing_form_id in missing_forms:
        response['errors'].append(
            _(u"Could not find XForm {form_id}").format(form_id=missing_form_id))

    return response
