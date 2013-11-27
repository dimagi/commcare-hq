from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from corehq.apps.accounting import models as accounting
from corehq.apps.sms.models import DIRECTION_CHOICES


class SmsGatewayFeeCriteria(models.Model):
    """
    These are the parameters we'll use to try and calculate the cost of sending a message through
    our gateways. We configure the SMS fee criteria based on parameters given to us by specific
    gateway providers.

    Nullable fields indicate criteria that can be applied globally to all messages with no specific matches
    for that field.
    """
    backend_api_id = models.CharField(max_length=100, db_index=True)
    backend_instance = models.CharField(max_length=255, db_index=True, null=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    country_code = models.CharField(max_length=5, null=True, db_index=True)


class SmsGatewayFee(models.Model):
    """
    The fee for sending or receiving an SMS Message based on gateway.
    When an SmsBillable is calculated, it will use the most recent SmsFee available from the criteria
    to determine the gateway_charge.

    Once an SmsFee is created, it cannot be modified.
    """
    criteria = models.ForeignKey(SmsGatewayFeeCriteria, on_delete=models.PROTECT)
    amount = models.FloatField(default=0.0)
    currency = models.ForeignKey(accounting.Currency, on_delete=models.PROTECT)
    date_created = models.DateField(auto_now_add=True)


class SmsUsageFeeCriteria(models.Model):
    """
    Criteria for determining a usage fee applied for each SMS message sent or received.

    Nullable fields indicate criteria that can be applied globally to all messages with no specific matches
    for that field.
    """
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    domain = models.CharField(max_length=25, db_index=True, null=True)


class SmsUsageFee(models.Model):
    """
    The usage fee, with version information, based on domain or globally.
    When an SmsBillable is calculated, it will use the most recent SmsUsageFee available from the
    criteria to determine the usage_charge.

    Currency is always in USD since this is something we control.

    Once an SmsUsageFee is created, it cannot be modified.
    """
    criteria = models.ForeignKey(SmsUsageFeeCriteria, on_delete=models.PROTECT)
    amount = models.FloatField(default=0.0)
    date_created = models.DateField(auto_now_add=True)


class SmsBillable(models.Model):
    """
    A record of matching a fee to a particular MessageLog (or SMSLog).

    If on closer inspection we determine a particular SmsBillable is invalid (whether something is
    awry with the api_response, or we used the incorrect fee and want to recalculate) we can set
    this billable to is_valid = False and it will not be used toward calculating the SmsLineItem in
    the monthly Invoice.
    """
    gateway_fee = models.ForeignKey(SmsGatewayFee, blank=True, on_delete=models.PROTECT)
    usage_fee = models.ForeignKey(SmsUsageFee, blank=True, on_delete=models.PROTECT)
    log_id = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=50)
    api_response = models.TextField(blank=True)
    is_valid = models.BooleanField(default=True, db_index=True)
    domain = models.CharField(max_length=25, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    date_sent = models.DateField()
    date_created = models.DateField(auto_now_add=True)

    @property
    def gateway_charge(self):
        try:
            charge = SmsGatewayFee.objects.get(id=self.gateway_fee.id)
            return charge.amount
        except ObjectDoesNotExist:
            return 0.0

    @property
    def usage_charge(self):
        try:
            charge = SmsUsageFee.objects.get(id=self.usage_fee.id)
            return charge.amount
        except ObjectDoesNotExist:
            return 0.0
