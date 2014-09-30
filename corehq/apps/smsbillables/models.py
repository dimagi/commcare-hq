import logging
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from corehq.apps.accounting import models as accounting
from corehq.apps.accounting.models import Currency
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES
from corehq.apps.sms.models import DIRECTION_CHOICES
from corehq.apps.sms.phonenumbers_helper import get_country_code
from corehq.apps.sms.util import clean_phone_number


smsbillables_logging = logging.getLogger("smsbillables")


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
    country_code = models.IntegerField(max_length=5, null=True, blank=True, db_index=True)

    @classmethod
    def get_most_specific(cls, backend_api_id, direction, backend_instance=None, country_code=None):
        """
        Gets the most specific criteria available based on (and in order of preference for optional):
        - backend_api_id
        - direction
        - backend_instance (optional)
        - country_code (optional)
        """
        all_possible_criteria = cls.objects.filter(backend_api_id=backend_api_id, direction=direction)

        if all_possible_criteria.count() == 0:
            return None

        try:
            return all_possible_criteria.get(country_code=country_code, backend_instance=backend_instance)
        except ObjectDoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=None, backend_instance=backend_instance)
        except ObjectDoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=country_code, backend_instance=None)
        except ObjectDoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=None, backend_instance=None)
        except ObjectDoesNotExist:
            pass

        return None


class SmsGatewayFee(models.Model):
    """
    The fee for sending or receiving an SMS Message based on gateway.
    When an SmsBillable is calculated, it will use the most recent SmsFee available from the criteria
    to determine the gateway_charge.

    Once an SmsFee is created, it cannot be modified.
    """
    criteria = models.ForeignKey(SmsGatewayFeeCriteria, on_delete=models.PROTECT)
    amount = models.DecimalField(default=0.0, max_digits=10, decimal_places=4)
    currency = models.ForeignKey(accounting.Currency, on_delete=models.PROTECT)
    date_created = models.DateField(auto_now_add=True)

    @classmethod
    def create_new(cls, backend_api_id, direction, amount,
                   currency=None, backend_instance=None, country_code=None, save=True):
        currency = currency or Currency.get_default()
        criteria, _ = SmsGatewayFeeCriteria.objects.get_or_create(
            backend_api_id=backend_api_id, direction=direction,
            backend_instance=backend_instance, country_code=country_code
        )
        new_fee = SmsGatewayFee(
            currency=currency,
            amount=amount,
            criteria=criteria
        )
        if save:
            new_fee.save()
        return new_fee


    @classmethod
    def get_by_criteria(cls, backend_api_id, direction, backend_instance=None, country_code=None):
        criteria = SmsGatewayFeeCriteria.get_most_specific(backend_api_id, direction,
                                                           backend_instance=backend_instance,
                                                           country_code=country_code)
        if not criteria:
            return None
        return cls.objects.filter(criteria=criteria.id).latest('date_created')


class SmsUsageFeeCriteria(models.Model):
    """
    Criteria for determining a usage fee applied for each SMS message sent or received.

    Nullable fields indicate criteria that can be applied globally to all messages with no specific matches
    for that field.
    """
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    domain = models.CharField(max_length=25, db_index=True, null=True)

    @classmethod
    def get_most_specific(cls, direction, domain=None):
        """
        Gets the most specific criteria available based on (and in order of preference for optional):
        - direction
        - domain (optional)
        """
        all_possible_criteria = cls.objects.filter(direction=direction)

        if all_possible_criteria.count() == 0:
            return None

        try:
            return all_possible_criteria.get(domain=domain)
        except ObjectDoesNotExist:
            pass
        try:
            return all_possible_criteria.get(domain=None)
        except ObjectDoesNotExist:
            pass

        return None


class SmsUsageFee(models.Model):
    """
    The usage fee, with version information, based on domain or globally.
    When an SmsBillable is calculated, it will use the most recent SmsUsageFee available from the
    criteria to determine the usage_charge.

    Currency is always in USD since this is something we control.

    Once an SmsUsageFee is created, it cannot be modified.
    """
    criteria = models.ForeignKey(SmsUsageFeeCriteria, on_delete=models.PROTECT)
    amount = models.DecimalField(default=0.0, max_digits=10, decimal_places=4)
    date_created = models.DateField(auto_now_add=True)

    @classmethod
    def create_new(cls, direction, amount, domain=None, save=True):
        criteria, _ = SmsUsageFeeCriteria.objects.get_or_create(
            domain=domain, direction=direction,
        )
        new_fee = SmsUsageFee(
            amount=amount,
            criteria=criteria
        )
        if save:
            new_fee.save()
        return new_fee

    @classmethod
    def get_by_criteria(cls, direction, domain=None):
        criteria = SmsUsageFeeCriteria.get_most_specific(direction, domain=domain)
        if not criteria:
            return None
        return cls.objects.filter(criteria=criteria.id).latest('date_created')


class SmsBillable(models.Model):
    """
    A record of matching a fee to a particular MessageLog (or SMSLog).

    If on closer inspection we determine a particular SmsBillable is invalid (whether something is
    awry with the api_response, or we used the incorrect fee and want to recalculate) we can set
    this billable to is_valid = False and it will not be used toward calculating the SmsLineItem in
    the monthly Invoice.
    """
    gateway_fee = models.ForeignKey(SmsGatewayFee, null=True, on_delete=models.PROTECT)
    gateway_fee_conversion_rate = models.DecimalField(default=Decimal('1.0'), null=True, max_digits=20,
                                                      decimal_places=EXCHANGE_RATE_DECIMAL_PLACES)
    usage_fee = models.ForeignKey(SmsUsageFee, null=True, on_delete=models.PROTECT)
    log_id = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=50)
    api_response = models.TextField(null=True, blank=True)
    is_valid = models.BooleanField(default=True, db_index=True)
    domain = models.CharField(max_length=25, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    date_sent = models.DateField()
    date_created = models.DateField(auto_now_add=True)

    @property
    def gateway_charge(self):
        if self.gateway_fee is not None:
            try:
                charge = SmsGatewayFee.objects.get(id=self.gateway_fee.id)
                if self.gateway_fee_conversion_rate is not None:
                    return charge.amount / self.gateway_fee_conversion_rate
                return charge.amount
            except ObjectDoesNotExist:
                pass
        return Decimal('0.0')

    @property
    def usage_charge(self):
        if self.usage_fee is not None:
            try:
                charge = SmsUsageFee.objects.get(id=self.usage_fee.id)
                return charge.amount
            except ObjectDoesNotExist:
                pass
        return Decimal('0.0')

    @classmethod
    def create(cls, message_log, api_response=None):
        phone_number = clean_phone_number(message_log.phone_number)
        direction = message_log.direction

        billable = cls(
            log_id=message_log._id,
            phone_number=phone_number,
            direction=direction,
            date_sent=message_log.date,
            domain=message_log.domain,
        )

        # Fetch gateway_fee
        backend_api_id = message_log.backend_api
        backend_instance = message_log.backend_id

        country_code = get_country_code(phone_number)

        billable.gateway_fee = SmsGatewayFee.get_by_criteria(
            backend_api_id, direction, backend_instance=backend_instance, country_code=country_code
        )
        if billable.gateway_fee is not None:
            conversion_rate = billable.gateway_fee.currency.rate_to_default
            if conversion_rate != 0:
                billable.gateway_fee_conversion_rate = conversion_rate
            else:
                smsbillables_logging.error("Gateway fee conversion rate for currency %s is 0",
                                           billable.gateway_fee.currency.code)

        # Fetch usage_fee todo
        domain = message_log.domain
        billable.usage_fee = SmsUsageFee.get_by_criteria(
            direction, domain=domain
        )

        if billable.usage_fee is None:
            smsbillables_logging.error("Did not find usage fee for direction %s and domain %s"
                                       % (direction, domain))

        if api_response is not None:
            billable.api_response = api_response

        billable.save()

        return billable
