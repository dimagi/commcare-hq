from django.contrib.postgres.fields import ArrayField
from django.db import models


class IPAccessConfig(models.Model):
    domain = models.CharField(max_length=126, db_index=True, unique=True)
    country_allowlist = ArrayField(models.CharField(max_length=2), default=list)
    ip_allowlist = ArrayField(models.GenericIPAddressField(), default=list)
    ip_denylist = ArrayField(models.GenericIPAddressField(), default=list)
    comment = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def is_allowed(self, ip_address):
        return (
            ip_address not in self.ip_denylist
            and (
                ip_address in self.ip_allowlist
                or is_in_country(ip_address, self.country_allowlist)
            )
        )


def is_in_country(ip_address, country_allowlist):
    # TODO
    return True
