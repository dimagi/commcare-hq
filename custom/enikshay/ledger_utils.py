from __future__ import absolute_import

from datetime import datetime
from collections import defaultdict

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.form_processor.exceptions import LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.util.quickcache import quickcache
from casexml.apps.stock.mock import (
    Balance,
    Entry,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from custom.enikshay.const import EPISODE_LEDGER_FIXTURE, EPISODE_LEDGER_SECTION_ID

LEDGER_UPDATE_DEVICE_ID = "%s.%s" % (__name__, 'reconcile_episode_ledger')


def get_episode_adherence_ledger(domain, episode_case_id, entry_id):
    """
    :param domain: domain name
    :param episode_case_id: episode case id for adherence
    :param entry_id: example date_2017-12-09
    """
    ledger_accessor = LedgerAccessors(domain)
    try:
        return ledger_accessor.get_ledger_value(episode_case_id, EPISODE_LEDGER_SECTION_ID, entry_id)
    except LedgerValueNotFound:
        return None


@quickcache(['domain'], memoize_timeout=7 * 24 * 60 * 60, timeout=7 * 24 * 60 * 60)
def _adherence_values_fixture_id(domain):
    fixture = FixtureDataType.by_domain_tag(domain, EPISODE_LEDGER_FIXTURE).first()
    if fixture:
        return fixture.get_id


@quickcache(['domain', 'fixture_id'], memoize_timeout=12 * 60 * 60, timeout=12 * 60 * 60)
def _get_all_fixture_items(domain, fixture_id):
    """
    :return: returns a dict mapped like
    defaultdict(dict,
            {u'99DOTS': {u'directly_observed_dose': u'13',
              u'manual': u'18',
              u'missed_dose': u'15',
              u'missing_data': u'16',
              u'self_administered_dose': u'17',
              u'unobserved_dose': u'14'},
             u'enikshay': {u'directly_observed_dose': u'1',
              u'manual': u'6',
              u'missed_dose': u'3',
              u'missing_data': u'4',
              u'self_administered_dose': u'5',
              u'unobserved_dose': u'2'},
            ...
            so one can use result[u'99DOTS'][u'missed_dose'] => 15
    """
    if fixture_id:
        all_items = FixtureDataItem.by_data_type(domain, fixture_id)
        result = defaultdict(dict)
        for item in all_items:
            source = item.fields['adherence_source'].field_list[0].field_value
            value = item.fields['adherence_value'].field_list[0].field_value
            ledger_value = item.fields['ledger_value'].field_list[0].field_value
            result[source][value] = ledger_value
        return result
    else:
        return defaultdict(dict)


def ledger_entry_id_for_adherence(adherence_date):
    return "date_%s" % adherence_date


def ledger_needs_update(domain, episode_case_id, entry_id, new_value):
    ledger = get_episode_adherence_ledger(domain, episode_case_id, entry_id)
    if ledger:
        return ledger.balance != new_value
    return True


def get_expected_fixture_value(domain, adherence_source, adherence_value):
    fixture_id = _adherence_values_fixture_id(domain)
    if fixture_id:
        return (_get_all_fixture_items(domain, fixture_id)
                [adherence_source]
                .get(adherence_value))


def _ledger_update_xml(episode_case_id, entry_id, ledger_value):
    balance = Balance()
    balance.entity_id = episode_case_id
    balance.date = datetime.utcnow()
    balance.section_id = EPISODE_LEDGER_SECTION_ID
    balance.entry = Entry(id=entry_id, quantity=ledger_value)
    return balance


def bulk_update_ledger_cases(domain, ledger_updates):
    case_blocks = []
    for episode_case_id, entry_id, balance in ledger_updates:
        balance = _ledger_update_xml(episode_case_id, entry_id, balance)
        case_blocks.append(balance.as_string())
    if case_blocks:
        submit_case_blocks(case_blocks, domain, device_id=LEDGER_UPDATE_DEVICE_ID)
