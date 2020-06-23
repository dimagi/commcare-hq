from collections import namedtuple
from decimal import Decimal

from django.conf import settings
from django.db import models

from corehq import toggles
from corehq.apps.accounting import models as accounting
from corehq.apps.accounting.models import Currency
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES
from corehq.apps.sms.models import (
    DIRECTION_CHOICES,
    INCOMING,
    OUTGOING,
    SQLMobileBackend,
)
from corehq.apps.sms.phonenumbers_helper import (
    get_country_code_and_national_number,
)
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.smsbillables.exceptions import (
    AmbiguousPrefixException,
    RetryBillableTaskException
)
from corehq.apps.smsbillables.utils import (
    log_smsbillables_error,
)
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.messaging.smsbackends.infobip.models import InfobipBackend
from corehq.messaging.smsbackends.amazon_pinpoint.models import PinpointBackend


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
    country_code = models.IntegerField(null=True, blank=True, db_index=True)
    prefix = models.CharField(max_length=10, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(object):
        app_label = 'smsbillables'

    @classmethod
    def get_most_specific(cls, backend_api_id, direction,
                          backend_instance=None, country_code=None, national_number=None):
        """
        Gets the most specific criteria available based on (and in order of preference for optional):
        - backend_api_id
        - direction
        - backend_instance (optional)
        - country_code and prefix (optional)
        """
        all_possible_criteria = cls.objects.filter(
            backend_api_id=backend_api_id,
            direction=direction,
            is_active=True,
        )

        if all_possible_criteria.count() == 0:
            return None

        national_number = national_number or ""

        def get_criteria_with_longest_matching_prefix(criteria_list):
            if len(set(criteria.prefix for criteria in criteria_list)) != len(criteria_list):
                raise AmbiguousPrefixException(
                    ", ".join(
                        "%(country_code)d, '%(prefix)s'" % {
                            "country_code": criteria.country_code,
                            "prefix": criteria.prefix,
                        } for criteria in criteria_list
                    )
                )
            criteria_list.sort(key=(lambda criteria: len(criteria.prefix)), reverse=True)
            for criteria in criteria_list:
                if national_number.startswith(criteria.prefix):
                    return criteria
            raise cls.DoesNotExist

        try:
            return get_criteria_with_longest_matching_prefix(
                list(all_possible_criteria.filter(country_code=country_code, backend_instance=backend_instance))
            )
        except cls.DoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=None, backend_instance=backend_instance)
        except cls.DoesNotExist:
            pass
        try:
            return get_criteria_with_longest_matching_prefix(
                list(all_possible_criteria.filter(country_code=country_code, backend_instance=None))
            )
        except cls.DoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=None, backend_instance=None)
        except cls.DoesNotExist:
            pass

        return None


class SmsGatewayFee(models.Model):
    """
    The fee for sending or receiving an SMS Message based on gateway.
    When an SmsBillable is calculated, it will use the most recent SmsGatewayFee available from the criteria
    to determine the gateway_charge.

    Once an SmsGatewayFee is created, it cannot be modified.
    """
    criteria = models.ForeignKey(SmsGatewayFeeCriteria, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=4, null=True)
    currency = models.ForeignKey(accounting.Currency, on_delete=models.PROTECT)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        app_label = 'smsbillables'

    @classmethod
    def create_new(cls, backend_api_id, direction, amount,
                   currency=None, backend_instance=None, country_code=None, prefix=None,
                   save=True, fee_class=None, criteria_class=None):
        fee_class = fee_class or cls
        criteria_class = criteria_class or SmsGatewayFeeCriteria
        currency = currency or Currency.get_default()

        if 'prefix' in [
            field.name
            for field in criteria_class._meta.get_fields()
        ]:
            prefix = prefix or ''
            criteria, _ = criteria_class.objects.get_or_create(
                backend_api_id=backend_api_id,
                direction=direction,
                backend_instance=backend_instance,
                country_code=country_code,
                prefix=prefix,
            )
        else:
            criteria, _ = criteria_class.objects.get_or_create(
                backend_api_id=backend_api_id,
                direction=direction,
                backend_instance=backend_instance,
                country_code=country_code,
            )
        new_fee = fee_class(
            currency=currency,
            amount=amount,
            criteria=criteria
        )
        if save:
            new_fee.save()
        return new_fee

    @classmethod
    def get_by_criteria(cls, backend_api_id, direction,
                        backend_instance=None, country_code=None, national_number=None):
        criteria = SmsGatewayFeeCriteria.get_most_specific(
            backend_api_id,
            direction,
            backend_instance=backend_instance,
            country_code=country_code,
            national_number=national_number,
        )
        return cls.get_by_criteria_obj(criteria)

    @classmethod
    def get_by_criteria_obj(cls, criteria):
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

    class Meta(object):
        app_label = 'smsbillables'

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
        except cls.DoesNotExist:
            pass
        try:
            return all_possible_criteria.get(domain=None)
        except cls.DoesNotExist:
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
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        app_label = 'smsbillables'

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
    A record of matching a fee to a particular SMS.

    If on closer inspection we determine a particular SmsBillable is invalid
    (we used the incorrect fee and want to recalculate)
    we can set this billable to is_valid = False and it will not be used toward
    calculating the SmsLineItem in the monthly Invoice.
    """
    gateway_fee = models.ForeignKey(SmsGatewayFee, null=True, on_delete=models.PROTECT)
    direct_gateway_fee = models.DecimalField(null=True, max_digits=10, decimal_places=4)
    gateway_fee_conversion_rate = models.DecimalField(default=Decimal('1.0'), null=True, max_digits=20,
                                                      decimal_places=EXCHANGE_RATE_DECIMAL_PLACES)
    usage_fee = models.ForeignKey(SmsUsageFee, null=True, on_delete=models.PROTECT)
    multipart_count = models.IntegerField(default=1)
    log_id = models.CharField(max_length=50, db_index=True)
    phone_number = models.CharField(max_length=50)
    is_valid = models.BooleanField(default=True, db_index=True)
    domain = models.CharField(max_length=100, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    date_sent = models.DateTimeField(db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        app_label = 'smsbillables'

    @property
    def gateway_charge(self):
        if self.direct_gateway_fee is None:
            return self.multipart_count * self._single_gateway_charge
        else:
            return self._single_gateway_charge

    @property
    def usage_charge(self):
        return self.multipart_count * self._single_usage_charge

    @property
    def _single_gateway_charge(self):
        amount = None
        if self.gateway_fee is not None:
            amount = self.gateway_fee.amount
        if amount is None:
            amount = self.direct_gateway_fee or Decimal('0.0')

        if self.gateway_fee_conversion_rate is not None:
            return amount / self.gateway_fee_conversion_rate
        return amount

    @property
    def _single_usage_charge(self):
        if self.usage_fee is not None:
            return self.usage_fee.amount
        return Decimal('0.0')

    @classmethod
    def create(cls, message_log, multipart_count=1):
        phone_number = clean_phone_number(message_log.phone_number)
        direction = message_log.direction
        domain = message_log.domain
        log_id = message_log.couch_id

        billable = cls(
            log_id=log_id,
            phone_number=phone_number,
            direction=direction,
            date_sent=message_log.date,
            domain=domain,
        )

        gateway_charge_info = cls._get_gateway_fee(
            message_log.backend_api, message_log.backend_id, phone_number, direction, log_id,
            message_log.backend_message_id, domain
        )
        billable.gateway_fee = gateway_charge_info.gateway_fee
        billable.gateway_fee_conversion_rate = gateway_charge_info.conversion_rate
        billable.direct_gateway_fee = gateway_charge_info.direct_gateway_fee
        billable.multipart_count = gateway_charge_info.multipart_count or multipart_count
        billable.usage_fee = cls._get_usage_fee(domain, direction)

        if message_log.backend_api == SQLTestSMSBackend.get_api_id():
            billable.is_valid = False

        billable.save()
        return billable

    @classmethod
    def _get_gateway_fee(cls, backend_api_id, backend_id,
                         phone_number, direction, couch_id, backend_message_id, domain):
        country_code, national_number = get_country_code_and_national_number(phone_number)
        backend_instance = SQLMobileBackend.load(
            backend_id,
            api_id=backend_api_id,
            is_couch_id=True,
            include_deleted=True,
        )

        is_gateway_billable = backend_id is None or backend_instance.is_global\
                              or toggles.ENABLE_INCLUDE_SMS_GATEWAY_CHARGING.enabled(domain)

        if is_gateway_billable:
            if hasattr(backend_instance, "get_provider_charges"):
                if backend_message_id:
                    status, price, multipart_count = backend_instance.get_provider_charges(backend_message_id)
                    if status is None or status.lower() in [
                        'accepted',
                        'queued',
                        'sending',
                        'receiving',
                    ] or price is None:
                        raise RetryBillableTaskException("backend_message_id=%s" % backend_message_id)
                    provider_charges = _ProviderChargeInfo(
                        abs(Decimal(price)),
                        SmsGatewayFee.get_by_criteria(
                            backend_api_id,
                            direction,
                        ),
                        multipart_count
                    )
                else:
                    log_smsbillables_error(
                        "Could not create gateway fee for message %s: no backend_message_id" % couch_id
                    )
                    provider_charges = _ProviderChargeInfo(None, None, None)

                gateway_fee = provider_charges.gateway_fee
                direct_gateway_fee = provider_charges.provider_gateway_fee
                multipart_count = provider_charges.multipart_count
            else:
                gateway_fee = SmsGatewayFee.get_by_criteria(
                    backend_api_id,
                    direction,
                    backend_instance=backend_instance,
                    country_code=country_code,
                    national_number=national_number,
                )
                direct_gateway_fee = None
                multipart_count = None
            if gateway_fee:
                conversion_rate = gateway_fee.currency.rate_to_default
                if conversion_rate != 0:
                    return _GatewayChargeInfo(gateway_fee, conversion_rate, direct_gateway_fee, multipart_count)
                else:
                    log_smsbillables_error(
                        "Gateway fee conversion rate for currency %s is 0"
                        % gateway_fee.currency.code
                    )
                    return _GatewayChargeInfo(gateway_fee, None, direct_gateway_fee, multipart_count)
            else:
                log_smsbillables_error(
                    "No matching gateway fee criteria for SMS %s" % couch_id
                )
        return _GatewayChargeInfo(None, None, None, None)

    @classmethod
    def _get_usage_fee(cls, domain, direction):
        usage_fee = SmsUsageFee.get_by_criteria(
            direction, domain=domain
        )
        if not usage_fee:
            log_smsbillables_error(
                "Did not find usage fee for direction %s and domain %s"
                % (direction, domain)
            )
        return usage_fee

_ProviderChargeInfo = namedtuple('_ProviderCharges', ['provider_gateway_fee', 'gateway_fee', 'multipart_count'])
_GatewayChargeInfo = namedtuple('_GatewayChargeInfo', ['gateway_fee', 'conversion_rate', 'direct_gateway_fee', 'multipart_count'])


def add_twilio_gateway_fee(apps):
    default_currency, _ = apps.get_model(
        'accounting', 'Currency'
    ).objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            SQLTwilioBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )


def add_infobip_gateway_fee(apps):
    default_currency, _ = apps.get_model(
        'accounting', 'Currency'
    ).objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            InfobipBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )


def add_pinpoint_gateway_fee(apps):
    default_currency, _ = apps.get_model(
        'accounting', 'Currency'
    ).objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            PinpointBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )
