from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


MAX_RECENT_UPLOADS = 100


def get_case_upload_records(domain, user, limit, skip=0):
    query_set = CaseUploadRecord.objects.filter(domain=domain)
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
        form = FormAccessors(case_upload.domain).get_form(form_record.form_id)
        for case_block in extract_case_blocks(form):
            yield case_block['@case_id']


def get_form_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        yield '{}\n'.format(form_record.form_id)
