"""
Tests for ``OpenmrsImporterForm``.

The posted importer JSON is user-supplied. Binding it to the form means
only declared fields can reach the document, and ``report_params`` is
validated before it is stored.
"""
import pytest

from corehq.motech.const import ALGO_AES_CBC, PASSWORD_PLACEHOLDER
from corehq.motech.openmrs.forms import OpenmrsImporterForm
from corehq.motech.openmrs.models import ColumnMapping, OpenmrsImporter

DOMAIN = 'test-domain'

VALID_DATA = {
    'server_url': 'http://www.example.com/openmrs',
    'username': 'admin',
    'password': 'Admin123',
    'report_uuid': 'c0ffee',
    'report_params': '{"endDate": "{{ today }}"}',
    'case_type': 'patient',
    'external_id_column': 'NID',
    'name_columns': 'givenName familyName',
    'column_map': '[{"column": "givenName", "property": "first_name"}]',
}


def get_form(**overrides):
    importer = OpenmrsImporter(domain=DOMAIN)
    form = OpenmrsImporterForm({**VALID_DATA, **overrides}, instance=importer)
    return form, importer


def test_save_sets_fields():
    form, importer = get_form()
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert importer.server_url == 'http://www.example.com/openmrs'
    assert importer.username == 'admin'
    assert importer.report_uuid == 'c0ffee'
    assert importer.report_params == {'endDate': '{{ today }}'}
    assert [m.to_json() for m in importer.column_map] == [
        ColumnMapping(column='givenName', property='first_name').to_json()
    ]


def test_save_returns_instance():
    form, importer = get_form()
    assert form.is_valid(), form.errors
    assert form.save(commit=False) is importer


def test_save_encrypts_password():
    form, importer = get_form()
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert importer.password.startswith(f'${ALGO_AES_CBC}$')
    assert 'Admin123' not in importer.password


def test_save_keeps_unchanged_password():
    importer = OpenmrsImporter(domain=DOMAIN, password='secret')
    form = OpenmrsImporterForm({**VALID_DATA, 'password': PASSWORD_PLACEHOLDER}, instance=importer)
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert importer.password == 'secret'


@pytest.mark.parametrize('field, expected', [
    ('import_frequency', 'monthly'),
    ('log_level', 40),
])
def test_save_keeps_choice_fields_when_blank(field, expected):
    importer = OpenmrsImporter(domain=DOMAIN, log_level=40)
    form = OpenmrsImporterForm({**VALID_DATA, field: ''}, instance=importer)
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert getattr(importer, field) == expected


def test_save_coerces_log_level():
    form, importer = get_form(log_level='20')
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert importer.log_level == 20


@pytest.mark.parametrize('key, value', [
    ('domain', 'other-domain'),
    ('_id', 'attacker-chosen-id'),
    ('_rev', '1-abc'),
    ('doc_type', 'WebUser'),
    ('not_a_field', 'x'),
])
def test_save_ignores_undeclared_fields(key, value):
    form, importer = get_form(**{key: value})
    assert form.is_valid(), form.errors
    form.save(commit=False)
    assert importer.domain == DOMAIN
    assert importer._id is None
    assert importer._rev is None
    assert importer.doc_type == 'OpenmrsImporter'
    assert 'not_a_field' not in importer.to_json()


@pytest.mark.parametrize('value', [
    '{"endDate": "{{ \'\'.__class__ }}"}',
    '{"endDate": "{{ today | upper }}"}',
    '{"endDate": "{% if today %}x{% endif %}"}',
])
def test_rejects_bad_report_params(value):
    form, importer = get_form(report_params=value)
    assert not form.is_valid()
    assert 'report_params' in form.errors
    assert importer.report_params == {}


def test_report_params_not_required():
    form, importer = get_form(report_params='')
    assert form.is_valid(), form.errors


@pytest.mark.parametrize('field', ['server_url', 'report_uuid', 'case_type'])
def test_required_fields(field):
    form, importer = get_form(**{field: ''})
    assert not form.is_valid()
    assert field in form.errors
