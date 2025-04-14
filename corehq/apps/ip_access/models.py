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

    def __repr__(self):
        return (
            f"IPAccessConfig('{self.domain}', "
            f"country_allowlist={self.country_allowlist}, "
            f"ip_allowlist={self.ip_allowlist}, "
            f"ip_denylist={self.ip_denylist})"
        )

    def is_allowed(self, ip_address):
        should_check_country = True
        if not self.country_allowlist:
            if not settings.MAXMIND_LICENSE_KEY:
                should_check_country = False
            elif ip_address not in self.ip_allowlist:
                return False
        return (
            ip_address not in self.ip_denylist
            and (
                ip_address in self.ip_allowlist
                or (should_check_country and is_in_country(ip_address, self.country_allowlist))
            )
        )


def get_ip_country(ip_address):
    with geoip2.webservice.Client(settings.MAXMIND_ACCOUNT_ID,
                                  settings.MAXMIND_LICENSE_KEY, host='geolite.info') as client:
        response = client.country(ip_address)
        metrics_counter('commcare.ip_access.check_country')
        return response.country.iso_code


def is_in_country(ip_address, country_allowlist):
    if get_ip_country(ip_address) in country_allowlist:
        return True
    return False
