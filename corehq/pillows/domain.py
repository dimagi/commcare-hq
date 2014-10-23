import copy
from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.pillows.base import HQPillow
from corehq.pillows.mappings.domain_mapping import DOMAIN_MAPPING, DOMAIN_INDEX
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings


class DomainPillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = Domain
    couch_filter = "domain/domains_inclusive"
    es_index_prefix = "hqdomains"
    es_alias = "hqdomains"
    es_type = "hqdomain"
    es_index = DOMAIN_INDEX
    default_mapping = DOMAIN_MAPPING
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                    "comma": {
                        "type": "pattern",
                        "pattern": "\s*,\s*"
                    },
                }
            }
        }
    }

    @memoized
    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return self.calc_mapping_hash({"es_meta": self.es_meta,
                                       "mapping": self.default_mapping})

    def change_transform(self, doc_dict):
        doc_ret = copy.deepcopy(doc_dict)
        sub =  Subscription.objects.filter(
                subscriber__domain=doc_dict['name'],
                is_active=True)
        if sub:
            doc_ret['subscription'] = sub[0].plan_version.plan.edition
        return doc_ret
