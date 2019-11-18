"""
This package is dedicated to parsing ledger xml as documented at
https://github.com/dimagi/commcare/wiki/ledgerxml

The quirks of ledger xml are outlined as follows.

There are two **Ledger Report Types**, 'balance' and 'transfer':

    <balance entity-id=""/>
and
    <transfer src="" dest="" type=""/>

There are also two **Ledger Report Formats**, 'individual' and 'per-entry'.

- Individual Ledger Balance:

    <balance xmlns="http://commcarehq.org/ledger/v1" entity-id="" date="" section-id="">
        <entry id="" quantity="" /> <!--multiple-->
    </balance>

  parsed into JSON as

    {"@xmlns": "http://commcarehq.org/ledger/v1", "@entity-id": "",
     "@date": "", "@section-id": "",
     "entry": [{"@id": "", "@quantity": ""}]}

- Per-Entry Ledger Balance:

    <balance xmlns="http://commcarehq.org/ledger/v1" entity-id="" date="">
        <entry id=""> <!--multiple-->
            <value section-id="" quantity=""/> <!-- multiple -->
        </entry>
    </balance>

  parsed into JSON as

    {"@xmlns": "http://commcarehq.org/ledger/v1", "@entity-id": "",
     "@date": "",
     "entry": [{"@id": "", "value": [{"@section-id: "", "@quantity": ""},
               ...]}]}

Conceptually, both formats produce a list of transactions:

    (entity_id="", date="", section_id="", entry_id="", quantity="")
    ...

but Per-Entry lets you have many different section_ids among the transactions.

"""


from .form import get_stock_actions
from .helpers import StockReportHelper, StockTransactionHelper
