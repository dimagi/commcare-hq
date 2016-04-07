import copy
from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.pillows.base import HQPillow
from corehq.pillows.mappings.domain_mapping import DOMAIN_MAPPING, DOMAIN_INDEX
from django_countries.data import COUNTRIES
from pillowtop.es_utils import doc_exists, get_index_info_from_pillow
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


class DomainPillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = Domain
    couch_filter = "domain/domains_inclusive"
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

    @classmethod
    def get_unique_id(self):
        return DOMAIN_INDEX

    def change_trigger(self, changes_dict):
        doc_dict = super(DomainPillow, self).change_trigger(changes_dict)
        if doc_dict and doc_dict['doc_type'] == 'Domain-DUPLICATE':
            if doc_exists(self, doc_dict):
                self.get_es_new().delete(self.es_index, self.es_type, doc_dict['_id'])
            return None
        else:
            return doc_dict

    def change_transform(self, doc_dict):
        doc_ret = copy.deepcopy(doc_dict)
        sub = Subscription.objects.filter(subscriber__domain=doc_dict['name'], is_active=True)
        doc_ret['deployment'] = doc_dict.get('deployment', None) or {}
        countries = doc_ret['deployment'].get('countries', [])
        doc_ret['deployment']['countries'] = []
        if sub:
            doc_ret['subscription'] = sub[0].plan_version.plan.edition
        for country in countries:
            doc_ret['deployment']['countries'].append(COUNTRIES[country].upper())
        return doc_ret


def get_domain_reindexer():
    pillow = DomainPillow(online=False)
    return ElasticPillowReindexer(
        pillow=pillow,
        change_provider=CouchViewChangeProvider(
            document_class=Domain,
            view_name='all_docs/by_doc_type',
            view_kwargs={
                'startkey': ['Domain'],
                'endkey': ['Domain', {}],
            }
        ),
        elasticsearch=pillow.get_es_new(),
        index_info=get_index_info_from_pillow(pillow),
    )
