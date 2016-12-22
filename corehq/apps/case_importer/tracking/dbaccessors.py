from corehq.apps.case_importer.tracking.models import CaseUploadRecord


def get_case_upload_records(domain, limit):
    return CaseUploadRecord.objects.filter(domain=domain).order_by('-created')[:limit]
