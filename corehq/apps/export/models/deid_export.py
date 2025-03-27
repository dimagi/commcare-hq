import uuid

from django.db import models

from dimagi.utils.data.deid_generator import DeidGenerator

from corehq.util.quickcache import quickcache


class DeIdHash(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.TextField(max_length=255, db_index=True)

    @classmethod
    def get_deid(cls, value, doc):
        if not value and not doc:
            return ''

        domain = doc['domain'] if isinstance(doc, dict) else doc.domain
        salt = cls._get_salt(domain)
        return DeidGenerator(value, salt).random_hash()

    @classmethod
    @quickcache(['domain'], timeout=24 * 60 * 60)
    def _get_salt(cls, domain):
        instance, __ = cls.objects.get_or_create(domain=domain)
        return instance.id.hex
