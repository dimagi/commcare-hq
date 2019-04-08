from __future__ import absolute_import
from __future__ import unicode_literals
from collections import Counter
import os
import re
import datetime
import json
import csv342 as csv
import sys
import tempfile

from django.conf import settings

from celery.task import task

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache
from corehq.apps.es import DomainES

from dimagi.utils.django.email import send_HTML_email

from soil.util import expose_zipped_blob_download
from couchexport.models import Format
from io import open


ADM_DOMAIN_KEY = 'ADM_ENABLED_DOMAINS'

new_domain_re = r"(?:[a-z0-9]+\-)*[a-z0-9]+" # lowercase letters, numbers, and '-' (at most one between "words")

grandfathered_domain_re = r"[a-z0-9\-\.:]+"
legacy_domain_re = r"[\w\.:-]+"
domain_url_re = re.compile(r'^/a/(?P<domain>%s)/' % legacy_domain_re)


def normalize_domain_name(domain):
    if domain:
        normalized = domain.replace('_', '-').lower()
        if settings.DEBUG:
            assert(re.match('^%s$' % grandfathered_domain_re, normalized))
        return normalized
    return domain


def get_domain_from_url(path):
    try:
        domain, = domain_url_re.search(path).groups()
    except Exception:
        domain = None
    return domain


@quickcache(['domain'])
def domain_restricts_superusers(domain):
    domain_obj = Domain.get_by_name(domain)
    if not domain_obj:
        return False
    return domain_obj.restrict_superusers


def user_has_custom_top_menu(domain_name, couch_user):
    """
    This is currently used for a one-off custom case (ewsghana)
    that required to be a toggle instead of a custom domain module setting
    """
    return (toggles.CUSTOM_MENU_BAR.enabled(domain_name) and
            not couch_user.is_superuser)


def get_domains_created_by_user(creating_user):
    query = DomainES().created_by_user(creating_user)
    data = query.run()
    return [d['name'] for d in data.hits]


@quickcache([], timeout=3600)
def domain_name_stop_words():
    path = os.path.join(os.path.dirname(__file__), 'static', 'domain', 'json')
    with open(os.path.join(path, 'stop_words.yml')) as f:
        return tuple([word.strip() for word in f.readlines() if word[0] != '#'])


def get_domain_url_slug(hr_name, max_length=25, separator='-'):
    from dimagi.utils.name_to_url import name_to_url
    name = name_to_url(hr_name, "project")
    if len(name) <= max_length:
        return name

    stop_words = domain_name_stop_words()
    words = [word for word in name.split('-') if word not in stop_words]
    words = iter(words)
    try:
        text = next(words)
    except StopIteration:
        return ''

    for word in words:
        if len(text + separator + word) <= max_length:
            text += separator + word

    return text[:max_length]


def guess_domain_language(domain_name):
    """
    A domain does not have a default language, but its apps do. Return
    the language code of the most common default language across apps.
    """
    domain_obj = Domain.get_by_name(domain_name)
    counter = Counter([app.default_language for app in domain_obj.applications() if not app.is_remote_app()])
    return counter.most_common(1)[0][0] if counter else 'en'


@task(serializer='pickle', queue='background_queue')
def send_repeater_payloads(repeater_id, payload_ids, email_id):
    from corehq.motech.repeaters.models import Repeater, RepeatRecord
    repeater = Repeater.get(repeater_id)
    repeater_type = repeater.doc_type
    payloads = dict()
    headers = ['note']
    result_file_name = "bulk-payloads-%s-%s-%s.csv" % (
        repeater.doc_type, repeater.get_id,
        datetime.datetime.utcnow().strftime("%Y-%m-%d--%H-%M-%S")
    )

    def get_payload(payload_id):
        dummy_repeat_record = RepeatRecord(
            domain=repeater.domain,
            next_check=datetime.datetime.utcnow(),
            repeater_id=repeater.get_id,
            repeater_type=repeater_type,
            payload_id=payload_id,
        )
        payload = repeater.get_payload(dummy_repeat_record)
        if isinstance(payload, dict):
            return payload
        else:
            return json.loads(payload)

    def populate_payloads(headers):
        for payload_id in payload_ids:
            try:
                payload = get_payload(payload_id)
                payloads[payload_id] = payload
                headers = list(set(headers + list(payload)))
            except Exception as e:
                payloads[payload_id] = {'note': 'Could not generate payload, %s' % str(e)}
        return headers

    def create_result_file():
        _, temp_file_path = tempfile.mkstemp()
        with open(temp_file_path, 'w') as csvfile:
            headers.append('payload_id')
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for payload_id, payload in payloads.items():
                row = payload
                row['payload_id'] = payload_id
                writer.writerow(row)
        return temp_file_path

    def email_result(download_url):
        send_HTML_email('Bulk Payload generated for %s' % repeater_type,
                        email_id,
                        'This email is to just let you know that there is a '
                        'download waiting for you at %s. It will expire in 24 hours' % download_url)

    headers = populate_payloads(headers)
    temp_file_path = create_result_file()
    download_url = expose_zipped_blob_download(
        temp_file_path,
        result_file_name,
        Format.CSV,
        repeater.domain,
    )
    email_result(download_url)


def silence_during_tests():
    if settings.UNIT_TESTING:
        return open(os.devnull, 'w')
    else:
        return sys.stdout
