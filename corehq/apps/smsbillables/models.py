from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from corehq.apps.accounting import models as accounting
from corehq.apps.accounting.models import Currency
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES
from corehq.apps.sms.models import DIRECTION_CHOICES, SQLMobileBackend
from corehq.apps.sms.phonenumbers_helper import get_country_code_and_national_number
from corehq.apps.smsbillables.utils import log_smsbillables_error
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.smsbillables.exceptions import AmbiguousPrefixException
from corehq.util.quickcache import quickcache


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
    prefix = models.CharField(max_length=10, blank=True, default="", db_index=True)

    class Meta:
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
        all_possible_criteria = cls.objects.filter(backend_api_id=backend_api_id, direction=direction)

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
            raise ObjectDoesNotExist

        try:
            return get_criteria_with_longest_matching_prefix(
                list(all_possible_criteria.filter(country_code=country_code, backend_instance=backend_instance))
            )
        except ObjectDoesNotExist:
            pass
        try:
            return all_possible_criteria.get(country_code=None, backend_instance=backend_instance)
        except ObjectDoesNotExist:
            pass
        try:
            return get_criteria_with_longest_matching_prefix(
                list(all_possible_criteria.filter(country_code=country_code, backend_instance=None))
            )
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
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
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
            for field, _ in criteria_class._meta.get_fields_with_model()
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

    class Meta:
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
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
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


@quickcache(['sms_backend_id'])
def _sms_backend_is_global(sms_backend_id):
    return SQLMobileBackend.load(
        sms_backend_id,
        is_couch_id=True,
        include_deleted=True
    ).is_global


class SmsBillable(models.Model):
    """
    A record of matching a fee to a particular SMS.

    If on closer inspection we determine a particular SmsBillable is invalid
    (we used the incorrect fee and want to recalculate)
    we can set this billable to is_valid = False and it will not be used toward
    calculating the SmsLineItem in the monthly Invoice.
    """
    gateway_fee = models.ForeignKey(SmsGatewayFee, null=True, on_delete=models.PROTECT)
    gateway_fee_conversion_rate = models.DecimalField(default=Decimal('1.0'), null=True, max_digits=20,
                                                      decimal_places=EXCHANGE_RATE_DECIMAL_PLACES)
    usage_fee = models.ForeignKey(SmsUsageFee, null=True, on_delete=models.PROTECT)
    multipart_count = models.IntegerField(null=True)
    log_id = models.CharField(max_length=50, db_index=True)
    phone_number = models.CharField(max_length=50)
    is_valid = models.BooleanField(default=True, db_index=True)
    domain = models.CharField(max_length=25, db_index=True)
    direction = models.CharField(max_length=10, db_index=True, choices=DIRECTION_CHOICES)
    date_sent = models.DateField()
    date_created = models.DateField(auto_now_add=True)

    class Meta:
        app_label = 'smsbillables'

    @property
    def gateway_charge(self):
        return (self.multipart_count if self.multipart_count is not None else 1) * self._single_gateway_charge

    @property
    def usage_charge(self):
        return (self.multipart_count if self.multipart_count is not None else 1) * self._single_usage_charge

    @property
    def _single_gateway_charge(self):
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
    def _single_usage_charge(self):
        if self.usage_fee is not None:
            try:
                charge = SmsUsageFee.objects.get(id=self.usage_fee.id)
                return charge.amount
            except ObjectDoesNotExist:
                pass
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
            multipart_count=multipart_count,
        )
        billable.gateway_fee, billable.gateway_fee_conversion_rate = cls._get_gateway_fee(
            message_log.backend_api, message_log.backend_id, phone_number, direction, log_id
        )
        billable.usage_fee = cls._get_usage_fee(domain, direction)

        if message_log.backend_api == SQLTestSMSBackend.get_api_id():
            billable.is_valid = False

        billable.save()
        return billable

    @classmethod
    def _get_gateway_fee(cls, backend_api_id, backend_instance, phone_number, direction, couch_id):
        country_code, national_number = get_country_code_and_national_number(phone_number)
        is_gateway_billable = backend_instance is None or _sms_backend_is_global(backend_instance)

        if is_gateway_billable:
            gateway_fee = SmsGatewayFee.get_by_criteria(
                backend_api_id,
                direction,
                backend_instance=backend_instance,
                country_code=country_code,
                national_number=national_number,
            )
            if gateway_fee:
                conversion_rate = gateway_fee.currency.rate_to_default
                if conversion_rate != 0:
                    return gateway_fee, conversion_rate
                else:
                    log_smsbillables_error(
                        "Gateway fee conversion rate for currency %s is 0"
                        % gateway_fee.currency.code
                    )
                    return gateway_fee, None
            else:
                log_smsbillables_error(
                    "No matching gateway fee criteria for SMS %s" % couch_id
                )
        return None, None

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
