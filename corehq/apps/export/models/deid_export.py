import uuid

from django.db import models

from dimagi.utils.data.deid_generator import DeidGenerator

from corehq.util.quickcache import quickcache


class DeIdHash(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.TextField(max_length=255, db_index=True)

    @classmethod
    def get_deid(cls, value, doc, domain=None):
        if not value and not doc:
            return None

        try:
            domain = (domain if domain is not None
                      else doc['domain'] if isinstance(doc, dict)
                      else doc.domain)
        except (AttributeError, KeyError):
            # this should only happen with bad form data, so don't try to de-identify anything

            # don't catch it for now, we want to see if this still comes up after domain is passed in
            # return None
            raise

        salt = cls._get_salt(domain)
        return DeidGenerator(value, salt).random_hash()

    @classmethod
    @quickcache(['domain'], timeout=24 * 60 * 60)
    def _get_salt(cls, domain):
        instance, __ = cls.objects.get_or_create(domain=domain)
        return instance.id.hex
