from __future__ import absolute_import
from __future__ import unicode_literals

from django.urls import reverse
from django.utils.functional import cached_property
from corehq.blobs import get_blob_db
from custom.icds_reports.models.helper import IcdsFile


class CCZHostingUtility:
    def __init__(self, ccz_hosting):
        self.ccz_hosting = ccz_hosting
        self.ccz_file_blob = None
        self._load_ccz_file()

    @cached_property
    def icds_file_obj(self):
        try:
            return IcdsFile.objects.get(blob_id=self.ccz_hosting.blob_id)
        except IcdsFile.DoesNotExist:
            return None

    def get_file(self):
        if self.ccz_file_blob:
            return self.ccz_file_blob.get_file_from_blobdb()

    def _load_ccz_file(self):
        if self.icds_file_obj:
            self.ccz_file_blob = IcdsFile.objects.get(blob_id=self.ccz_hosting.blob_id)

    @cached_property
    def ccz_file_meta(self):
        db = get_blob_db()
        return db.metadb.get(key=self.ccz_hosting.blob_id, parent_id='IcdsFile')

    @property
    def ccz_details(self):
        if self.ccz_file_blob:
            return {
                'name': self.ccz_hosting.file_name or self.ccz_file_meta.name,
                'download_url': reverse('ccz_hosting_download_ccz', args=[
                    self.ccz_hosting.domain, self.ccz_hosting.id, self.ccz_hosting.blob_id])
            }
        return {}
