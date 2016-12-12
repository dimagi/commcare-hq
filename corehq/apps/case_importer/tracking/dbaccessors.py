from corehq.apps.case_importer.tracking.models import CaseUploadRecord, CaseUploadJSON


def get_case_uploads(domain, limit):
    return map(
        CaseUploadJSON.from_model,
        CaseUploadRecord.objects.filter(domain=domain).order_by('-created')[:limit]
    )
