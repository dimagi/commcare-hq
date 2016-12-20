from corehq.apps.case_importer.tracking.models import CaseUploadRecord


def get_case_upload_records(domain, limit):
    return CaseUploadRecord.objects.filter(domain=domain).order_by('-created')[:limit]


def get_case_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        for case_record in form_record.case_records.order_by('pk').all():
            yield case_record.case_id


def get_form_ids_for_case_upload(case_upload):
    for form_record in case_upload.form_records.order_by('pk').all():
        yield '{}\n'.format(form_record.form_id)
