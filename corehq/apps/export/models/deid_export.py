import uuid
from hashlib import md5

from django.db import models

from corehq.util.quickcache import quickcache


class DeIdHash(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.TextField(max_length=255, db_index=True)

    @classmethod
    def get_deid(cls, value, doc):
        domain = doc['domain'] if isinstance(doc, dict) else doc.domain
        salt = cls._get_salt(domain)
        data = f'{value}{salt}'.encode('utf-8')
        return md5(data).hexdigest()

    @classmethod
    @quickcache(['domain'], timeout=24 * 60 * 60)
    def _get_salt(cls, domain):
        instance, __ = cls.objects.get_or_create(domain=domain)
        return instance.id.hex
