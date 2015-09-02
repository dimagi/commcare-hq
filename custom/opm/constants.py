from corehq.apps.fixtures.models import FixtureDataItem
from corehq.util.quickcache import quickcache

DOMAIN = 'opm'

PREG_REG_XMLNS = "http://openrosa.org/formdesigner/D127C457-3E15-4F5E-88C3-98CD1722C625"
VHND_XMLNS = "http://openrosa.org/formdesigner/ff5de10d75afda15cddb3b00a0b1e21d33a50d59"
BIRTH_PREP_XMLNS = "http://openrosa.org/formdesigner/50378991-FEC3-408D-B4A5-A264F3B52184"
DELIVERY_XMLNS = "http://openrosa.org/formdesigner/492F8F0E-EE7D-4B28-B890-7CDA5F137194"
CHILD_FOLLOWUP_XMLNS = "http://openrosa.org/formdesigner/C90C2C1F-3B34-47F3-B3A3-061EAAC1A601"
CFU1_XMLNS = "http://openrosa.org/formdesigner/d642dd328514f2af92c093d414d63e5b2670b9c"
CFU2_XMLNS = "http://openrosa.org/formdesigner/9ef423bba8595a99976f0bc9532617841253a7fa"
CFU3_XMLNS = "http://openrosa.org/formdesigner/f15b9f8fb92e2552b1885897ece257609ed16649"
GROWTH_MONITORING_XMLNS= "http://openrosa.org/formdesigner/F1356F3F-C695-491F-9277-7F9B5522200C"

CLOSE_FORM = "http://openrosa.org/formdesigner/41A1B3E0-C1A4-41EA-AE90-71A328F0D8FD"
CHILDREN_FORMS = [CFU1_XMLNS, CFU2_XMLNS, CFU3_XMLNS, CHILD_FOLLOWUP_XMLNS]

OPM_XMLNSs = [PREG_REG_XMLNS, VHND_XMLNS, BIRTH_PREP_XMLNS, DELIVERY_XMLNS,
              CHILD_FOLLOWUP_XMLNS, CFU1_XMLNS, CFU2_XMLNS, CFU3_XMLNS,
              GROWTH_MONITORING_XMLNS, CLOSE_FORM]

# TODO Move these to a cached fixtures lookup
MONTH_AMT = 250
TWO_YEAR_AMT = 2000
THREE_YEAR_AMT = 3000


@quickcache([], timeout=30 * 60)
def get_fixture_data():
    fixtures = FixtureDataItem.get_indexed_items(DOMAIN, 'condition_amounts', 'condition')
    return dict((k, int(fixture['rs_amount'])) for k, fixture in fixtures.items())


class InvalidRow(Exception):
    """
    Raise this in the row constructor to skip row
    """


class CaseOutOfRange(InvalidRow):
    """
    The row is invalid because the window calculations are out of range.
    """
