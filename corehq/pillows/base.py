from pillowtop.listener import AliasedElasticPillow
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings


VALUE_TAG = '#value'

def map_types(item, mapping, override_root_keys=None):
    if isinstance(item, dict):
        return convert_property_dict(item, mapping, override_root_keys=override_root_keys)
    elif isinstance(item, list):
        return [map_types(x, mapping) for x in item]
    else:
        return {VALUE_TAG: item}

def convert_property_dict(sub_dict, mapping, override_root_keys=None):
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
        dynamic_mapping = mapping.get('dynamic', True)
        sub_mapping = mapping.get('properties', {}).get(k, {})
        if dynamic_mapping is not False:
            sub_dict[k] = map_types(v, sub_mapping, override_root_keys=override_root_keys)
    return sub_dict

def restore_property_dict(report_dict_item):
    """
    Revert a converted/retrieved document from Report<index> and deconvert all its properties
    back from {#value: <val>} to just <val>
    """
    restored = {}
    if not isinstance(report_dict_item, dict):
        return report_dict_item

    for k, v in report_dict_item.items():
        if isinstance(v, list):
            restored[k] = [restore_property_dict(x) for x in v]
        elif isinstance(v, dict):
            if VALUE_TAG in v:
                restored[k] = v[VALUE_TAG]
            else:
                restored[k] = restore_property_dict(v)
        else:
            restored[k] = v

    return restored



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
                    "sortable_exact": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["lowercase"]
                    }
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

