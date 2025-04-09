import geoip2.webservice

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from corehq.util.metrics import metrics_counter


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
    # If there is no countries in the allowlist, assume all countries are allowed
    # If MaxMind is not configured in the env, default to blocking all requests
    if not country_allowlist:
        return True
    if not settings.MAXMIND_LICENSE_KEY:
        return False

    with geoip2.webservice.Client(settings.MAXMIND_ACCOUNT_ID,
                                  settings.MAXMIND_LICENSE_KEY, host='geolite.info') as client:
        response = client.country(ip_address)
        metrics_counter('commcare.ip_access.check_country')
        if response.country.iso_code in country_allowlist:
            return True
        else:
            return False
