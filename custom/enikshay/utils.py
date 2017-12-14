from __future__ import absolute_import

from datetime import datetime

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.models import LedgerValue
from corehq.util.quickcache import quickcache
from custom.enikshay.case_utils import get_episode_case_from_adherence


def get_episode_adherence_ledger(domain, episode_case_id, entry_id):
    """
    :param domain: domain name
    :param episode_case_id: episode case id for adherence
    :param entry_id: example date_2017-12-09
    """
    ledger_accessor = LedgerAccessors(domain)
    return ledger_accessor.get_ledger_value(episode_case_id, "adherence", entry_id)


@quickcache(['domain', 'adherence_source'], memoize_timeout=12 * 60 * 60, timeout=12 * 60 * 60)
def get_fixture_items_for_adherence_source(domain, adherence_source):
    """
    currently this would be few cached FixtureDataItem objects
    Can also consider turning the fixture in a key => value pair with key being the
    adherence source and adherence value mapped to the ledger value
    and combine with the next set of calculation to get fixture_item_for_value
    """
    fixture = FixtureDataType.by_domain_tag(domain, "adherence_ledger_values").first()
    if fixture:
        return FixtureDataItem.by_field_value(domain, fixture,
                                              "adherence_source", adherence_source).all()
    else:
        return None


def update_ledger_with_episode(episode_case, adherence_case, entry_id):
    """
    :param episode_case: episode case for the adherence
    :param entry_id: example "date_2017-12-09" which would be the adherence date
    """
    adherence_source = adherence_case.get_case_property('adherence_source')
    adherence_value = adherence_case.get_case_property('adherence_value')
    if adherence_source and adherence_value:
        fixture_items_for_source = get_fixture_items_for_adherence_source(
            adherence_case.domain, adherence_source
        )
        if fixture_items_for_source:
            fixture_items_for_value = [
                fixture_item for fixture_item in fixture_items_for_source
                if fixture_item.fields['adherence_value'].field_list[0].field_value == adherence_value
            ]
            if fixture_items_for_value:
                fixture_item = fixture_items_for_source[0]
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


def update_ledger_for_adherence(adherence_case, episode_case=None):
    if not episode_case:
        episode_case = get_episode_case_from_adherence(adherence_case.domain, adherence_case.case_id)

    adherence_date = adherence_case.get_case_property('adherence_date')
    if adherence_date:
        entry_id = "date_%s" % adherence_date
        update_ledger_with_episode(episode_case, adherence_case, entry_id)
