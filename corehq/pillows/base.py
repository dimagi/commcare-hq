from pillowtop.listener import AliasedElasticPillow
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings


VALUE_TAG = '#value'

def convert_properties(sub_dict, mapping, override_root_keys=None):
    """
    For mapping out ALL nested properties on cases, convert everything to a dict so as to
    prevent string=>object and object=>string mapping errors.

    sub_dict: the doc dict you want to modify in place before sending to ES
    mapping: The mapping at the level of the properties you are at - originally passing as the default mapping of the pillow
    override_root_keys: a list of keys you want explicitly skipped at the root level and are not recursed down
    """
    mapping = mapping or {}
    override_root_keys = override_root_keys or []

    for k, v in sub_dict.items():
        if k in mapping.get('properties', {}) or k in override_root_keys:
            continue

        if isinstance(v, dict):
            if mapping.get('dynamic', False):
                #only transmogrify stuff if it's explicitly set to dynamic
                sub_dict[k] = convert_properties(v, mapping.get('properties', {}).get(k, {}))
        else:
            sub_dict[k] = {VALUE_TAG: v}
    return sub_dict


class HQPillow(AliasedElasticPillow):
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 60
    default_mapping = None
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }

    def __init__(self, **kwargs):
        super(HQPillow, self).__init__(**kwargs)

    @memoized
    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        return self.calc_mapping_hash(self.default_mapping)

    def get_domain(self, doc_dict):
        """
        A cache/buffer for the _changes feed situation for xforms.
        """
        return doc_dict.get('domain', None)

    def get_type_string(self, doc_dict):
        return self.es_type

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the domain_type document.
        See below on why date_detection is False

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all are strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

