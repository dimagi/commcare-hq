from dimagi.utils.decorators.memoized import memoized

DOMAIN = 'opm'

PREG_REG_XMLNS = "http://openrosa.org/formdesigner/D127C457-3E15-4F5E-88C3-98CD1722C625"
VHND_XMLNS = "http://openrosa.org/formdesigner/ff5de10d75afda15cddb3b00a0b1e21d33a50d59"
BIRTH_PREP_XMLNS = "http://openrosa.org/formdesigner/50378991-FEC3-408D-B4A5-A264F3B52184"
DELIVERY_XMLNS = "http://openrosa.org/formdesigner/492F8F0E-EE7D-4B28-B890-7CDA5F137194"
CHILD_FOLLOWUP_XMLNS = "http://openrosa.org/formdesigner/C90C2C1F-3B34-47F3-B3A3-061EAAC1A601"


@memoized
def get_fixture_data():
    fixtures = {
        'two_year_cash': 250,
        'three_year_cash': 250
    }
    return fixtures

FIXTURES = get_fixture_data()