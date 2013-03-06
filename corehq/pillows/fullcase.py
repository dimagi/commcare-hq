from django.conf import settings
from corehq.pillows.case import CasePillow

from corehq.pillows.mappings.fullcase_mapping import FULL_CASE_MAPPING, FULL_CASE_INDEX


UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"

class FullCasePillow(CasePillow):
    """
    Simple/Common Case properties Indexer
    """
    es_index_prefix = "full_cases"
    es_alias = "full_cases"
    es_type = "fullcase"
    es_index = FULL_CASE_INDEX
    default_mapping = FULL_CASE_MAPPING

    def change_trigger(self, changes_dict):
        """
        Override and check to ensure that the opened doc's domain matches
        those enabled for fully indexed case docs
        """
        doc_dict = super(FullCasePillow, self).change_trigger(changes_dict)
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = UNKNOWN_DOMAIN

        dynamic_domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        if domain in dynamic_domains:
            return doc_dict
        else:
            return None


    def get_type_string(self, doc_dict):
        """
        Unique ES type key for each case
        """
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = UNKNOWN_DOMAIN
        case_type = doc_dict.get('type', None)
        if case_type is None:
            case_type = UNKNOWN_TYPE

        ret = "%(type)s_%(domain)s__%(case_type)s" % {
            'type': self.es_type,
            'domain': domain.lower(),
            'case_type': case_type.lower(),
        }
        return ret
