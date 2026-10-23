"""
Tests for applying posted importer JSON to an ``OpenmrsImporter``.

The posted JSON is user-supplied, so only an explicit allow-list of
fields may be set on the document.
"""
import json

import pytest

from corehq.motech.const import ALGO_AES_CBC, PASSWORD_PLACEHOLDER
from corehq.motech.openmrs.models import ColumnMapping, OpenmrsImporter
from corehq.motech.openmrs.views import update_importer

DOMAIN = 'test-domain'


def test_update_importer_sets_allowed_fields():
    importer = OpenmrsImporter(domain=DOMAIN)
    update_importer(importer, {
        'server_url': 'http://www.example.com/openmrs',
        'username': 'admin',
        'report_uuid': 'c0ffee',
        'report_params': json.dumps({'endDate': '{{ today }}'}),
        'column_map': json.dumps([{'column': 'givenName', 'property': 'first_name'}]),
    })
    assert importer.server_url == 'http://www.example.com/openmrs'
    assert importer.username == 'admin'
    assert importer.report_uuid == 'c0ffee'
    assert importer.report_params == {'endDate': '{{ today }}'}
    assert [m.to_json() for m in importer.column_map] == [
        ColumnMapping(column='givenName', property='first_name').to_json()
    ]


def test_update_importer_encrypts_password():
    importer = OpenmrsImporter(domain=DOMAIN)
    update_importer(importer, {'password': 'Admin123'})
    assert importer.password.startswith(f'${ALGO_AES_CBC}$')
    assert 'Admin123' not in importer.password


def test_update_importer_keeps_unchanged_password():
    importer = OpenmrsImporter(domain=DOMAIN, password='secret')
    update_importer(importer, {'password': PASSWORD_PLACEHOLDER})
    assert importer.password == 'secret'


@pytest.mark.parametrize('key, value', [
    ('domain', 'other-domain'),
    ('_id', 'attacker-chosen-id'),
    ('_rev', '1-abc'),
    ('doc_type', 'WebUser'),
    ('not_a_field', 'x'),
])
def test_update_importer_ignores_other_keys(key, value):
    importer = OpenmrsImporter(domain=DOMAIN)
    before = importer.to_json()
    update_importer(importer, {key: value})
    assert importer.to_json() == before
    assert importer.domain == DOMAIN


def test_update_importer_rejects_bad_report_params():
    importer = OpenmrsImporter(domain=DOMAIN)
    with pytest.raises(ValueError):
        update_importer(importer, {
            'report_params': json.dumps({'endDate': "{{ ''.__class__ }}"}),
        })
    assert importer.report_params == {}
