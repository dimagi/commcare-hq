from csv import DictWriter
from io import StringIO

from django.contrib.postgres.fields import JSONField
from django.db import models


class UserUploadRecord(models.Model):
    domain = models.CharField(max_length=256)
    result = JSONField(null=True)
    task_id = models.CharField(max_length=40)
    date_created = models.DateTimeField(auto_now_add=True)
    user_id = models.CharField(max_length=40)

    def get_file(self):
        csvfile = StringIO()
        fieldnames = list(self.status['rows'][0]['row'].keys())
        writer = DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in self.status['rows']:
            writer.writerow(row['row'])
        csvfile.seek(0)
        return csvfile
