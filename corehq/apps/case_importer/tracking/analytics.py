from django.db.models import Sum

from corehq.apps.case_importer.tracking.models import CaseUploadFileMeta


def get_case_upload_files_total_bytes():
    return CaseUploadFileMeta.objects.aggregate(Sum('length'))['length__sum']
