from django.db import models

class MigrationCheckpoint(models.Model):
     domain = models.CharField(max_length=100)
     date = models.DateTimeField()