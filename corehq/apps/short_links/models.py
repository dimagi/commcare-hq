import secrets
import string

from django.db import models
from django.db.models import Q
from django.utils import timezone

from dimagi.utils.web import get_url_base

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 12


def make_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for __ in range(CODE_LENGTH))


class ShortLinkQuerySet(models.QuerySet):

    def active(self):
        return self.exclude(expires_at__lt=timezone.now())


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
    expires_at = models.DateTimeField(null=True)

    objects = ShortLinkQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=['domain', 'target_url'])]

    @classmethod
    def shorten(cls, domain, target_url, expires_at=None):
        """Get or create a short URL standing in for an absolute ``target_url``.

        Re-uses an existing link with an expiration greater than or equal to
        expires_at, or one that has no expiration.
        """

        expiration_filter = Q(expires_at__isnull=True)
        if expires_at:
            expiration_filter = (expiration_filter | Q(expires_at__gte=expires_at))

        link = cls.objects.active().filter(
            expiration_filter,
            domain=domain,
            target_url=target_url,
        ).order_by('created_at').first() or cls.objects.create(
            domain=domain, target_url=target_url, expires_at=expires_at,
        )

        return link

    @property
    def short_url(self):
        return f'{get_url_base()}/s/{self.code}'
