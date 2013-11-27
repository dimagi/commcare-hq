from django.db import models

from corehq.apps.accounting import models as accounting
from corehq.apps.sms.models import DIRECTION_CHOICES


class SmsRate(models.Model):
    """
    These are the parameters we'll use to try and calculate the cost of sending a message through
    our gateways.
    When attempting to find an SmsRate for a message sent, we will try to match most specific rate
    (all null fields filled out) to least specific rate if no specific rates are matched.
    If no matching rates are found, only a DIMAGI_SMS_USAGE_FEE will be applied.
    """
    backend_api_id = models.CharField(max_length=100, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    country_code = models.CharField(max_length=5, null=True, db_index=True)


class SmsRateVersion(models.Model):
    """
    The rate for a particular backend api, direction, and country code match may change over time.
    This is how we'll keep track of those changes, by adding a date_created field. When an SmsBillable
    is calculated, it will use the most recent SmsRateVersion available to determine the gateway_charge.
    """
    rate = models.ForeignKey(SmsRate, on_delete=models.PROTECT)
    fee = models.FloatField(default=0.0)
    currency = models.ForeignKey(accounting.Currency, on_delete=models.PROTECT)
    date_created = models.DateField(auto_now_add=True)


class SmsBillable(models.Model):
    """
    A record of applying a charge to a particular MessageLog (or SMSLog).
    Every message log sent will have one of these Billables, even on custom SmsBackends, as there will be
    a usage charge for each message sent.
    """
    rate_version = models.ForeignKey(SmsRate, blank=True, on_delete=models.PROTECT)
    log_id = models.CharField(max_length=50)
    domain = models.CharField(max_length=25, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    phone_number = models.CharField(max_length=50)
    gateway_charge = models.FloatField(default=0.0)
    usage_charge = models.FloatField(default=0.0)
    api_response = models.TextField(blank=True)
    is_valid = models.BooleanField(default=True, db_index=True)
    date_sent = models.DateField()
    date_created = models.DateField(auto_now_add=True)
