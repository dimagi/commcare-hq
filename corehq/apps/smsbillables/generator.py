import random
import datetime
import string
from decimal import Decimal

from dimagi.utils.data import generator as data_gen
from corehq.apps.sms.models import INCOMING, OUTGOING, SMSLog
from corehq.apps.sms.util import get_available_backends


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

TEST_COUNTRY_CODES = [1, 20, 30, 220, 501]
OTHER_COUNTRY_CODES = [31, 40, 245, 502]

DIRECTIONS = [INCOMING, OUTGOING]


def arbitrary_message():
    return random.choice(SMS_MESSAGE_CONTENT)


def arbitrary_fee():
    return Decimal(str(round(random.uniform(0.0, 1.0), 4)))


def arbitrary_phone_number(country_codes=TEST_COUNTRY_CODES):
    return str(random.choice(country_codes)) + str(random.randint(10**9, 10**10 - 1))


def arbitrary_domain(length=25):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))


def arbitrary_fees_by_direction():
    fees = {}
    for direction in DIRECTIONS:
        fees[direction] = arbitrary_fee()
    return fees


def arbitrary_fees_by_direction_and_domain():
    domains = [arbitrary_domain() for i in range(10)]
    fees = {}
    for direction in DIRECTIONS:
        fees_by_domain = {}
        for domain in domains:
            fees_by_domain[domain] = arbitrary_fee()
        fees[direction] = fees_by_domain
    return fees


def arbitrary_fees_by_direction_and_backend():
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in get_available_backends().values():
            fees_by_backend[backend.get_api_id()] = arbitrary_fee()
        fees[direction] = fees_by_backend
    return fees


def arbitrary_fees_by_country():
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in get_available_backends().values():
            fees_by_country = {}
            for country in TEST_COUNTRY_CODES:
                fees_by_country[country] = arbitrary_fee()
            fees_by_backend[backend.get_api_id()] = fees_by_country
        fees[direction] = fees_by_backend
    return fees


def arbitrary_fees_by_backend_instance(backend_ids):
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in get_available_backends().values():
            fees_by_backend[backend.get_api_id()] = (backend_ids[backend.get_api_id()], arbitrary_fee())
        fees[direction] = fees_by_backend
    return fees


def arbitrary_fees_by_all(backend_ids):
    fees = {}
    for direction in DIRECTIONS:
        fees_by_backend = {}
        for backend in get_available_backends().values():
            fees_by_country = {}
            for country in TEST_COUNTRY_CODES:
                fees_by_country[country] = (backend_ids[backend.get_api_id()], arbitrary_fee())
            fees_by_backend[backend.get_api_id()] = fees_by_country
        fees[direction] = fees_by_backend
    return fees


def arbitrary_backend_ids():
    backend_ids = {}
    for backend in get_available_backends().values():
        backend_ids[backend.get_api_id()] = data_gen.arbitrary_unique_name("back")
    return backend_ids


def arbitrary_messages_by_backend_and_direction(backend_ids,
                                                phone_number=None,
                                                domain=None,
                                                directions=DIRECTIONS):
    phone_number = phone_number or TEST_NUMBER
    domain = domain or TEST_DOMAIN
    messages = []
    for api_id, instance_id in backend_ids.items():
        for direction in directions:
            sms_log = SMSLog(
                direction=direction,
                phone_number=phone_number,
                domain=domain,
                backend_api=api_id,
                backend_id=instance_id,
                text=arbitrary_message(),
                date=datetime.datetime.now()
            )
            sms_log.save()
            messages.append(sms_log)
    return messages
