import geoip2.webservice

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from corehq.util.metrics import metrics_counter

from no_exceptions.exceptions import Http403


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
        if ip_address in self.ip_denylist or (self.country_allowlist and not settings.MAXMIND_LICENSE_KEY):
            return False
        elif not self.country_allowlist or ip_address in self.ip_allowlist:
            return True
        return is_in_country(ip_address, self.country_allowlist)


def get_ip_country(ip_address):
    try:
        with geoip2.webservice.Client(settings.MAXMIND_ACCOUNT_ID,
                                      settings.MAXMIND_LICENSE_KEY, host='geolite.info') as client:
            response = client.country(ip_address)
            metrics_counter('commcare.ip_access.check_country')
            return response.country.iso_code
    except geoip2.errors.AuthenticationError:
        raise Http403(_("Please provide a valid MaxMind license key and Account ID to filter IPs by country. "
                      "If you do not have a MaxMind account, please clear the Allowed Countries field in the "
                      "IP Access Config to access your project."))


def is_in_country(ip_address, country_allowlist):
    if get_ip_country(ip_address) in country_allowlist:
        return True
    return False
