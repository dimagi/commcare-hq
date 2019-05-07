from __future__ import absolute_import
from __future__ import unicode_literals

from django.urls import reverse
from django.utils.functional import cached_property

from custom.icds_reports.models.helper import IcdsFile


class CCZHostingUtility:
    def __init__(self, ccz_hosting):
        self.ccz_hosting = ccz_hosting
        self.ccz_file_blob = None

    @cached_property
    def icds_file_obj(self):
        try:
            return IcdsFile.objects.get(blob_id=self.ccz_hosting.blob_id)
        except IcdsFile.DoesNotExist:
            return None

    def get_file(self):
        if self.icds_file_obj:
            return self.icds_file_obj.get_file_from_blobdb()

    @cached_property
    def ccz_file_meta(self):
        if self.icds_file_obj:
            return self.icds_file_obj.get_file_meta

    @property
    def ccz_details(self):
        if self.icds_file_obj:
            return {
                'name': self.ccz_hosting.file_name or self.ccz_file_meta.name,
                'download_url': reverse('ccz_hosting_download_ccz', args=[
                    self.ccz_hosting.domain, self.ccz_hosting.id, self.ccz_hosting.blob_id])
            }
        return {}
