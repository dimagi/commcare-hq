from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


def get_case_upload_records(domain, limit):
    return CaseUploadRecord.objects.filter(domain=domain).order_by('-created')[:limit]


def get_case_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        form = FormAccessors(case_upload.domain).get_form(form_record.form_id)
        for case_block in extract_case_blocks(form):
            yield case_block['@case_id']


def get_form_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        yield '{}\n'.format(form_record.form_id)
