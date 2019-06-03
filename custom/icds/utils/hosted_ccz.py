from __future__ import absolute_import
from __future__ import unicode_literals

from memoized import memoized
from django.urls import reverse

from corehq.blobs import (
    get_blob_db,
    CODES,
)


class HostedCCZUtility:
    def __init__(self, file_hosting):
        self.domain = file_hosting.domain
        self.file_hosting = file_hosting
        self.blob_id = file_hosting.blob_id

    def file_exists(self):
        return get_blob_db().exists(key=self.blob_id)

    def get_file(self):
        return get_blob_db().get(key=self.blob_id)

    def get_file_size(self):
        return get_blob_db().size(key=self.blob_id)

    @memoized
    def get_file_meta(self):
        if self.file_exists():
            return get_blob_db().metadb.get(key=self.blob_id, parent_id='HostedCCZ')

    def get_file_name(self):
        return self.get_file_meta().name if self.get_file_meta() else ''

    @property
    def ccz_details(self):
        return {
            'name': self.file_hosting.file_name,
            'download_url': reverse('hosted_ccz_download_ccz', args=[
                self.domain, self.file_hosting.id])
        }

    def store_file_in_blobdb(self, file_obj, name):
        kw = {
            "domain": self.file_hosting.domain,
            "parent_id": 'HostedCCZ',
            "type_code": CODES.tempfile,
            "key": self.blob_id,
            "name": name,
        }
        get_blob_db().put(file_obj, **kw)

    def remove_file_from_blobdb(self):
        get_blob_db().delete(key=self.blob_id)
