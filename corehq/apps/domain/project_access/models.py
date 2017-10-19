import datetime
from django.db import models

ENTRY_RECORD_FREQUENCY = datetime.timedelta(hours=6)


class SuperuserProjectEntryRecord(models.Model):
    username = models.EmailField()
    project = models.CharField(max_length=256)
    last_login = models.DateTimeField(auto_now=True)

    @classmethod
    def record_entry(cls, username, domain):
        record = cls(username=username, project=domain)
        record.save()

    @classmethod
    def entry_recently_recorded(cls, username, domain):
        return cls.objects.filter(
            username=username,
            project=domain,
            last_login__gt=datetime.datetime.utcnow() - ENTRY_RECORD_FREQUENCY,
        ).count() > 0
