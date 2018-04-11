from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.pillows.mappings.utils import mapping_from_json
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo


LEDGER_INDEX = es_index("ledgers_2016-03-15")
LEDGER_ALIAS = "ledgers"
LEDGER_TYPE = "ledger"
LEDGER_MAPPING = mapping_from_json('ledger_mapping.json')


LEDGER_INDEX_INFO = ElasticsearchIndexInfo(
    index=LEDGER_INDEX,
    alias=LEDGER_ALIAS,
    type=LEDGER_TYPE,
    mapping=LEDGER_MAPPING,
)
