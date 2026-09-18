import secrets
import string

from django.db import IntegrityError, models, transaction

from dimagi.utils.retry import retry_on
from dimagi.utils.web import get_url_base

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 12


def make_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for __ in range(CODE_LENGTH))


class ShortLink(models.Model):
    """A code that redirects to a longer URL.

    ``target_url`` is absolute and is redirected to verbatim -- only ever pass
    a URL built by HQ, never one derived from user input.

    ``domain`` records which project created the code, for cleanup on deletion.
    """

    code = models.CharField(max_length=32, primary_key=True, default=make_code)
    domain = models.CharField(max_length=255, null=True)
    target_url = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['domain', 'target_url'])]

    @property
    def short_url(self):
        return f'{get_url_base()}/s/{self.code}'

    @classmethod
    @retry_on(IntegrityError, delays=[0, 0])
    @transaction.atomic
    def shorten(cls, domain, target_url):
        short_link, __ = cls.objects.get_or_create(domain=domain, target_url=target_url)
        return short_link
