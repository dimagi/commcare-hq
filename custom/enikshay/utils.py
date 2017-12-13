from __future__ import absolute_import

from datetime import datetime

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.models import LedgerValue


def get_episode_adherence_ledger(domain, episode_case_id, entry_id):
    """
    :param domain: domain name
    :param episode_case_id: episode case id for adherence
    :param entry_id: example date_2017-12-09
    """
    ledger_accessor = LedgerAccessors(domain)
    return ledger_accessor.get_ledger_value(episode_case_id, "adherence", entry_id)


def update_ledger_with_episode(episode_case, adherence_case, entry_id):
    """
    :param episode_case: episode case for the adherence
    :param entry_id: example "date_2017-12-09" which would be the adherence date
    """
    adherence_source = adherence_case.get_case_property('adherence_source')
    adherence_value = adherence_case.get_case_property('adherence_value')
    fixture = FixtureDataType.by_domain_tag(adherence_case.domain, "adherence_ledger_values").first()
    fixture_items_for_source = FixtureDataItem.by_field_value(
        adherence_case.domain, fixture,
        "adherence_source", adherence_source).all()
    fixture_items_for_value = [
        fixture_item for fixture_item in fixture_items_for_source
        if fixture_item.fields['adherence_value'].field_list[0].field_value == adherence_value
    ]
    fixture_item = fixture_items_for_value[0]
    ledger_value = fixture_item.fields['ledger_value'].field_list[0].field_value
    ledger = get_episode_adherence_ledger(episode_case.domain, episode_case.case_id, entry_id)
    if ledger:
        ledger.balance = ledger_value
        ledger.save()
    else:
        ledger = LedgerValue(
            domain=adherence_case.domain,
            case_id=episode_case.case_id,
            section_id="adherence",
            entry_id=entry_id,
            balance=ledger_value,
            last_modified=datetime.utcnow()
        )
    LedgerAccessorSQL.save_ledger_values([ledger])
    return ledger
