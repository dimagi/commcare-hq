from django.db import models

class BackupRecord(models.Model):
    last_update = models.DateField(auto_now_add=False, null=False)
