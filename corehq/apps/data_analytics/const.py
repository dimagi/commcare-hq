from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.const import AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET


YES = True
NO = False
NOT_SET = None
AMPLIFY_COUCH_TO_SQL_MAP = {
    AMPLIFIES_YES: YES,
    AMPLIFIES_NO: NO,
    AMPLIFIES_NOT_SET: NOT_SET
}
TEST_COUCH_TO_SQL_MAP = {
    "true": YES,
    "false": NO,
    "none": NOT_SET
}

BU_MAPPING = {
    "AF": "DSI",
    "AO": "DSA",
    "BD": "DSI",
    "BZ": "DLAC",
    "BJ": "DWA",
    "BR": "DLAC",
    "BF": "DWA",
    "BI": "DSA",
    "CM": "DWA",
    "CA": "INC",
    "TD": "DWA",
    "CN": "NA",
    "CO": "DLAC",
    "DO": "DLAC",
    "EG": "INC",
    "ET": "DSA",
    "FR": "INC",
    "GM": "DWA",
    "GH": "DWA",
    "GD": "DLAC",
    "GT": "DLAC",
    "GN": "DWA",
    "HT": "DLAC",
    "HN": "DLAC",
    "IN": "DSI",
    "ID": "DSI",
    "IQ": "INC",
    "JO": "INC",
    "KE": "DSA",
    "LA": "DSI",
    "LS": "DSA",
    "LR": "DWA",
    "MG": "DSA",
    "MW": "DSA",
    "MY": "DSI",
    "ML": "DWA",
    "MX": "DLAC",
    "MZ": "DMOZ",
    "MM": "DSI",
    "NA": "DSA",
    "NP": "DSI",
    "NI": "DLAC",
    "NE": "DWA",
    "NG": "DWA",
    "PK": "DSI",
    "PE": "DLAC",
    "PH": "DSI",
    "RW": "DSA",
    "SN": "DWA",
    "SL": "DWA",
    "ZA": "DSA",
    "SS": "DSA",
    "ES": "INC",
    "LK": "DSI",
    "SY": "INC",
    "TZ": "DSA",
    "TH": "DSI",
    "TL": "DSI",
    "TG": "DWA",
    "TR": "INC",
    "UG": "DSA",
    "GB": "INC",
    "US": "INC",
    "VN": "DSI",
    "ZM": "DSA",
    "ZW": "DSA",
}

GIR_FIELDS = [
    "Project Space",
    "Country",
    "Sector",
    "Subsector",
    "Business Unit",
    "Self Service",
    "Test Domain",
    "Domain Start Date",
    "Dominant Device Type",
    "Active Users",
    "Eligible for WAMs",
    "Eligible for PAMs",
    "WAMs current month",
    "WAMs 1 month prior",
    "WAMs 2 months prior",
    "Active Users current month",
    "Active Users 1 month prior",
    "Active Users 2 months prior",
    "Using and Performing",
    "Not Performing",
    "Inactive and Experienced",
    "Inactive and Not Experienced",
    "Not Experienced",
    "Not Performing and Not Experienced",
    "D1 All Users Ever Active",
    "D2 All Possibly Exp Users",
    "D3 All Ever Exp Users",
    "D4 All Experienced + Active Users",
    "D5 All Active Users",
    "D6 All Active Users Current + Prior 2 Mos",
    "Eligible Forms",
    "Experienced Threshold",
    "Performance Threshold",
]

NO_BU = "MISSING BU"

DEFAULT_PERFORMANCE_THRESHOLD = 15
DEFAULT_EXPERIENCED_THRESHOLD = 3
DEFAULT_ACCESS_THRESHOLD = 20
