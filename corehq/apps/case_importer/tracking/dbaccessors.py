from casexml.apps.case.xform import extract_case_blocks

from django.db.models import Q

from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.form_processor.models import XFormInstance
from corehq.apps.enterprise.models import EnterprisePermissions

MAX_RECENT_UPLOADS = 10000


def get_case_upload_records(domain, user, limit, skip=0, query=''):
    query_set = CaseUploadRecord.objects.filter(domain=domain)
    if query:
        query_set = query_set.filter(
            Q(upload_file_meta__filename__icontains=query)
            | Q(comment__icontains=query)
        )
    if not user.has_permission(domain, 'access_all_locations'):
        query_set = query_set.filter(couch_user_id=user._id)
    return query_set.order_by('-created')[skip:skip + limit]


def get_case_upload_record_count(domain, user):
    query_set = CaseUploadRecord.objects.filter(domain=domain)
    if not user.has_permission(domain, 'access_all_locations'):
        query_set = query_set.filter(couch_user_id=user._id)
    return min(MAX_RECENT_UPLOADS, query_set.count())


def get_case_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        if EnterprisePermissions.is_source_domain(case_upload.domain):
            form = XFormInstance.objects.get_form(form_record.form_id)
        else:
            form = XFormInstance.objects.get_form(form_record.form_id, case_upload.domain)
        for case_block in extract_case_blocks(form):
            yield case_block['@case_id']


def get_form_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        yield '{}\n'.format(form_record.form_id)
