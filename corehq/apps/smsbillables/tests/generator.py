from __future__ import absolute_import
from builtins import range
import calendar
import random
import datetime
import string
import uuid
from collections import namedtuple
from decimal import Decimal

from dimagi.utils.data import generator as data_gen

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING, SMS
from corehq.apps.sms.util import get_sms_backend_classes
from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee, SmsUsageFee
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.util.test_utils import unit_testing_only
from six.moves import range


# arbitrarily generated once from http://www.generatedata.com/

SMS_MESSAGE_CONTENT = [
    "Nullam scelerisque neque sed sem", "non massa non ante bibendum", "lectus, a sollicitudin orci sem",
    "felis, adipiscing fringilla, porttitor vulputate", "nibh. Phasellus nulla. Integer vulputate",
    "pede, malesuada vel, venenatis vel", "molestie arcu. Sed eu nibh", "non nisi. Aenean eget metus.",
    "luctus. Curabitur egestas nunc sed", "risus. Nulla eget metus eu", "penatibus et magnis dis parturient",
    "malesuada ut, sem. Nulla interdum.", "diam luctus lobortis. Class aptent", "enim. Nunc ut erat. Sed",
    "pede. Praesent eu dui. Cum", "Duis ac arcu. Nunc mauris.", "vel nisl. Quisque fringilla euismod",
    "consequat purus. Maecenas libero est", "ultrices posuere cubilia Curae; Donec", "hymenaeos. Mauris ut quam vel",
    "dolor quam, elementum at, egestas", "Praesent eu dui. Cum sociis", "nisl. Quisque fringilla euismod enim.",
    "nunc, ullamcorper eu, euismod ac", "varius orci, in consequat enim", "convallis ligula. Donec luctus aliquet"
]

TEST_DOMAIN = "test"
TEST_NUMBER = "16175005454"

TEST_COUNTRY_CODES = (1, 20, 30, 220, 501)
OTHER_COUNTRY_CODES = (31, 40, 245, 502)

DIRECTIONS = [INCOMING, OUTGOING]

CountryPrefixPair = namedtuple('CountryPrefixPair', ['country_code', 'prefix'])


@unit_testing_only
def arbitrary_message():
    return random.choice(SMS_MESSAGE_CONTENT)


@unit_testing_only
def arbitrary_fee():
    return Decimal(str(round(random.uniform(0.0, 1.0), 4)))


@unit_testing_only
def _generate_prefixes(country_code, max_prefix_length, num_prefixes_per_size):
    def _generate_prefix(cc, existing_prefixes, i):
        while True:
            prefix = existing_prefixes[-1 - i] + str(random.randint(0 if cc != 1 else 2, 9))
            if prefix not in existing_prefixes:
                return prefix

    prefixes = [""]
    for _ in range(max_prefix_length):
        for i in range(num_prefixes_per_size):
            prefixes.append(_generate_prefix(country_code, prefixes, i))
    return prefixes


@unit_testing_only
def arbitrary_country_code_and_prefixes(
    max_prefix_length, num_prefixes_per_size,
    country_codes=TEST_COUNTRY_CODES
):
    return [
        CountryPrefixPair(str(country_code), prefix)
        for country_code in country_codes
        for prefix in _generate_prefixes(country_code, max_prefix_length, num_prefixes_per_size)
    ]


@unit_testing_only
def _available_gateway_fee_backends():
    return [
        backend for backend in get_sms_backend_classes().values()
        if backend.get_api_id() != SQLTwilioBackend.get_api_id()
    ]


@unit_testing_only
def arbitrary_fees_by_prefix(backend_ids, country_codes_and_prefixes):
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in _available_gateway_fee_backends():
            fees_by_country_code = {}
            for country_code, _ in country_codes_and_prefixes:
                fees_by_country_code[country_code] = {}
            for country_code, prefix in country_codes_and_prefixes:
                fees_by_prefix = {
                    backend_instance: arbitrary_fee()
                    for backend_instance in [backend_ids[backend.get_api_id()], None]
                }
                fees_by_country_code[country_code][prefix] = fees_by_prefix
            fees_by_backend[backend.get_api_id()] = fees_by_country_code
        fees[direction] = fees_by_backend
    return fees


@unit_testing_only
def arbitrary_phone_number(country_codes=TEST_COUNTRY_CODES):
    return str(random.choice(country_codes)) + str(random.randint(10**9, 10**10 - 1))


@unit_testing_only
def arbitrary_domain(length=25):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))


@unit_testing_only
def arbitrary_fees_by_direction():
    fees = {}
    for direction in DIRECTIONS:
        fees[direction] = arbitrary_fee()
    return fees


@unit_testing_only
def arbitrary_fees_by_direction_and_domain():
    domains = [arbitrary_domain() for i in range(10)]
    fees = {}
    for direction in DIRECTIONS:
        fees_by_domain = {}
        for domain in domains:
            fees_by_domain[domain] = arbitrary_fee()
        fees[direction] = fees_by_domain
    return fees


@unit_testing_only
def arbitrary_fees_by_direction_and_backend():
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in _available_gateway_fee_backends():
            fees_by_backend[backend.get_api_id()] = arbitrary_fee()
        fees[direction] = fees_by_backend
    return fees


@unit_testing_only
def arbitrary_fees_by_country():
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in _available_gateway_fee_backends():
            fees_by_country = {}
            for country in TEST_COUNTRY_CODES:
                fees_by_country[country] = arbitrary_fee()
            fees_by_backend[backend.get_api_id()] = fees_by_country
        fees[direction] = fees_by_backend
    return fees


@unit_testing_only
def arbitrary_fees_by_backend_instance(backend_ids):
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in _available_gateway_fee_backends():
            fees_by_backend[backend.get_api_id()] = (backend_ids[backend.get_api_id()], arbitrary_fee())
        fees[direction] = fees_by_backend
    return fees


@unit_testing_only
def arbitrary_fees_by_all(backend_ids):
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in _available_gateway_fee_backends():
            fees_by_country = {}
            for country in TEST_COUNTRY_CODES:
                fees_by_country[country] = (backend_ids[backend.get_api_id()], arbitrary_fee())
            fees_by_backend[backend.get_api_id()] = fees_by_country
        fees[direction] = fees_by_backend
    return fees


@unit_testing_only
def arbitrary_backend_ids():
    backend_ids = {}
    for backend in _available_gateway_fee_backends():
        backend_instance = data_gen.arbitrary_unique_name("back")
        backend_ids[backend.get_api_id()] = backend_instance
        sms_backend = backend()
        sms_backend.hq_api_id = backend.get_api_id()
        sms_backend.couch_id = backend_instance
        sms_backend.name = backend_instance
        sms_backend.is_global = True
        sms_backend.save()
    return backend_ids


@unit_testing_only
def arbitrary_messages_by_backend_and_direction(backend_ids,
                                                phone_number=None,
                                                domain=None,
                                                directions=None):
    phone_number = phone_number or TEST_NUMBER
    domain = domain or TEST_DOMAIN
    directions = directions or DIRECTIONS
    messages = []
    for api_id, instance_id in backend_ids.items():
        for direction in directions:
            sms_log = SMS(
                direction=direction,
                phone_number=phone_number,
                domain=domain,
                backend_api=api_id,
                backend_id=instance_id,
                backend_message_id=uuid.uuid4().hex,
                text=arbitrary_message(),
                date=datetime.datetime.utcnow()
            )
            sms_log.save()
            messages.append(sms_log)
    return messages


@unit_testing_only
def arbitrary_currency():
    return Currency.objects.get_or_create(
        code='OTH',
        defaults={
            'rate_to_default': Decimal('%5.f' % random.uniform(0.5, 2.0)),
        },
    )[0]


@unit_testing_only
def arbitrary_phone_numbers_and_prefixes(country_code_and_prefixes):
    country_code_to_prefixes = {}
    for country_code, prefix in country_code_and_prefixes:
        if country_code not in country_code_to_prefixes:
            country_code_to_prefixes[country_code] = []
        country_code_to_prefixes[country_code].append(prefix)
    for country_code, prefix in country_code_and_prefixes:
        remainder_len = 10 - len(prefix)

        def _get_national_number():
            return prefix + str(random.randint(
                (1 if prefix else 2) * (10 ** (remainder_len - 1)),
                (10 ** remainder_len) - 1
            ))

        while True:
            national_number = _get_national_number()
            if not any(
                national_number.startswith(another_prefix) and another_prefix.startswith(prefix)
                for another_prefix in country_code_to_prefixes[country_code]
                if another_prefix and another_prefix != prefix
            ):
                yield (
                    country_code + national_number,
                    prefix
                )
                break


@unit_testing_only
def arbitrary_sms_billables_for_domain(domain, message_month_date, num_sms, direction=None, multipart_count=1):
    direction = direction or random.choice(DIRECTIONS)

    gateway_fee = SmsGatewayFee.create_new('MACH', direction, Decimal(0.5))
    usage_fee = SmsUsageFee.create_new(direction, Decimal(0.25))

    _, last_day_message = calendar.monthrange(message_month_date.year, message_month_date.month)

    billables = []
    for _ in range(0, num_sms):
        sms_billable = SmsBillable(
            gateway_fee=gateway_fee,
            usage_fee=usage_fee,
            log_id=data_gen.arbitrary_unique_name()[:50],
            phone_number=data_gen.random_phonenumber(),
            domain=domain,
            direction=direction,
            date_sent=datetime.date(message_month_date.year, message_month_date.month,
                                    random.randint(1, last_day_message)),
            multipart_count=multipart_count,
        )
        sms_billable.save()
        billables.append(sms_billable)
    return billables
