import uuid

from csv import DictWriter
from io import BytesIO

from django.contrib.postgres.fields import JSONField
from django.db import models

from corehq.blobs import CODES, get_blob_db


class UserUploadRecord(models.Model):
    domain = models.TextField()
    status = JSONField(null=True)
    task_id = models.CharField(max_length=256)
    date_created = models.DateTimeField(auto_now_add=True)

    def get_file(self):
        f = BytesIO()
        with open(f, 'w') as csvfile:
            fieldnames = list(self.status['rows']['row'][0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.status['rows']:
                writer.writerow(row['row'])
        f.seek(0)
        return f
