from __future__ import absolute_import
import datetime
import architect
from django.db import models

ENTRY_RECORD_FREQUENCY = datetime.timedelta(hours=6)


@architect.install('partition', type='range', subtype='date', constraint='month', column='last_login')
class SuperuserProjectEntryRecord(models.Model):
    username = models.EmailField(db_index=True)
    domain = models.CharField(max_length=256)
    last_login = models.DateTimeField(auto_now=True)

    class Meta(object):
        index_together = ['domain', 'username']

    @classmethod
    def record_entry(cls, username, domain):
        record = cls(username=username, domain=domain)
        record.save()

    @classmethod
    def entry_recently_recorded(cls, username, domain):
        return cls.objects.filter(
            username=username,
            domain=domain,
            last_login__gt=datetime.datetime.utcnow() - ENTRY_RECORD_FREQUENCY,
        ).exists()
