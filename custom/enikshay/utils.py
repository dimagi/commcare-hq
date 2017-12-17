from __future__ import absolute_import

from datetime import datetime
from collections import defaultdict

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.util.quickcache import quickcache
from casexml.apps.stock.mock import (
    Balance,
    Entry,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import SYSTEM_USER_ID


def get_episode_adherence_ledger(domain, episode_case_id, entry_id):
    """
    :param domain: domain name
    :param episode_case_id: episode case id for adherence
    :param entry_id: example date_2017-12-09
    """
    ledger_accessor = LedgerAccessors(domain)
    return ledger_accessor.get_ledger_value(episode_case_id, "adherence", entry_id)


@quickcache(['domain'], memoize_timeout=7 * 24 * 60 * 60, timeout=7 * 24 * 60 * 60)
def get_id_of_fixture_tagged_adherence_ledger_values(domain):
    fixture = FixtureDataType.by_domain_tag(domain, "adherence_ledger_values").first()
    if fixture:
        return fixture.get_id


@quickcache(['domain', 'fixture_id'], memoize_timeout=12 * 60 * 60, timeout=12 * 60 * 60)
def get_all_fixture_items(domain, fixture_id):
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
        return {}


def update_ledger_with_episode(episode_case, entry_id, adherence_source, adherence_value):
    """
    :param episode_case: episode case for the adherence
    :param entry_id: example "date_2017-12-09" which would be the adherence date
    """
    def needs_update(new_value):
        ledger = get_episode_adherence_ledger(domain, episode_case.case_id, entry_id)
        if ledger:
            return ledger.balance != new_value
        return True

    domain = episode_case.domain
    if adherence_source and adherence_value:
        fixture_id = get_id_of_fixture_tagged_adherence_ledger_values(domain)
        if fixture_id:
            ledger_value = get_all_fixture_items(
                domain,
                fixture_id
            ).get(adherence_source, {}).get(adherence_value)
            if ledger_value:
                if needs_update(ledger_value):
                    balance = Balance()
                    balance.entity_id = episode_case.case_id
                    balance.date = datetime.utcnow()
                    balance.section_id = "adherence"
                    entry = Entry()
                    entry.id = entry_id
                    entry.quantity = ledger_value
                    balance.entry = entry
                    return submit_case_blocks([balance.as_string()],
                                              episode_case.domain,
                                              SYSTEM_USER_ID)


def update_ledger_for_adherence(episode_case, adherence_date, adherence_source, adherence_value):
    entry_id = "date_%s" % adherence_date
    update_ledger_with_episode(episode_case, entry_id, adherence_source, adherence_value)
