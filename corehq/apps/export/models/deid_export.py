import hashlib
import uuid

from django.db import models

from corehq.const import ONE_DAY
from corehq.util.quickcache import quickcache


class DeIdMapping(models.Model):
    domain = models.TextField(max_length=255)
    hashed_value = models.TextField(max_length=32)
    deid = models.UUIDField(default=uuid.uuid4)

    class Meta:
        indexes = [
            models.Index(fields=['domain', 'hashed_value']),
        ]

    @classmethod
    def get_deid(cls, value, doc, domain=None):
        if doc is not None:
            # use domain from the couch doc if one was passed in
            domain = doc['domain']

        return cls._get_deid(value, domain)

    @classmethod
    @quickcache(['value', 'domain'], timeout=90 * ONE_DAY)
    def _get_deid(cls, value, domain):
        hashed_value = cls._hash_value(value)
        deid_mapping, __ = cls.objects.get_or_create(domain=domain, hashed_value=hashed_value)
        return deid_mapping.deid

    @staticmethod
    @quickcache(['value'], timeout=90 * ONE_DAY)
    def _hash_value(value):
        if value is None:
            # None is a de-identifiable value but needs a string to encode for lookup
            value = ''

        return hashlib.md5(value.encode('utf-8')).hexdigest()
