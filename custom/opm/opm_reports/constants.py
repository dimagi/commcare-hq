from dimagi.utils.decorators.memoized import memoized
from corehq.apps.fixtures.models import FixtureDataItem

DOMAIN = 'opm'

PREG_REG_XMLNS = "http://openrosa.org/formdesigner/D127C457-3E15-4F5E-88C3-98CD1722C625"
VHND_XMLNS = "http://openrosa.org/formdesigner/ff5de10d75afda15cddb3b00a0b1e21d33a50d59"
BIRTH_PREP_XMLNS = "http://openrosa.org/formdesigner/50378991-FEC3-408D-B4A5-A264F3B52184"
DELIVERY_XMLNS = "http://openrosa.org/formdesigner/492F8F0E-EE7D-4B28-B890-7CDA5F137194"
CHILD_FOLLOWUP_XMLNS = "http://openrosa.org/formdesigner/C90C2C1F-3B34-47F3-B3A3-061EAAC1A601"

def get_fixture_amt(raw, k, v):
    for fixture in raw:
        if fixture.get(k) and (fixture.get(k) == v):
            value = int(fixture["Amount (Rs.)"])
            # not sure if I should use this assertion
            assert value != 0, "One of the fixtures returned a zero cash amount"
            return value


@memoized
def get_fixture_data():
    raw = [f.to_json().get('fields') for f in FixtureDataItem.by_domain('opm').all()]
    fixtures = {
        'two_year_cash': get_fixture_amt(raw, "Time Difference", "2 years"),
        'three_year_cash': get_fixture_amt(raw, "Time Difference", "3 years"),
        'service_forms_cash': get_fixture_amt(
            raw, "If 1 VHND form submitted", "Form Submission"),
        'growth_monitoring_cash': get_fixture_amt(
            raw, "Form Property", "/data/child_1/child1_child_growthmon = '1'"),
        'birth_preparedness_cash': get_fixture_amt(
            raw, "Form Property", "window_1_1 = \"1\""),
        'child_followup': 125,
    }
    return fixtures


FIXTURES = get_fixture_data()