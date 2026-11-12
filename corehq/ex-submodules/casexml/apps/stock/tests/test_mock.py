from datetime import datetime

from casexml.apps.stock.mock import Balance, Entry


def test_from_xml_round_trips_balance():
    balance = Balance(
        entity_id='entity-1',
        date=datetime(2024, 1, 1),
        entry=Entry(id='item-1', quantity=5),
    )

    round_tripped = Balance.from_xml(balance.as_xml())

    assert round_tripped.entity_id == balance.entity_id
    assert round_tripped.date == balance.date
    assert round_tripped.entry.id == balance.entry.id
    assert round_tripped.entry.quantity == balance.entry.quantity
