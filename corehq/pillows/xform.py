import copy
from casexml.apps.case.xform import extract_case_blocks
from corehq.pillows.case import UNKNOWN_DOMAIN, UNKNOWN_TYPE
from corehq.pillows.core import DATE_FORMATS_ARR
from corehq.pillows.mappings.xform_mapping import XFORM_MAPPING, XFORM_INDEX
from dimagi.utils.decorators.memoized import memoized
from .base import HQPillow
from pillowtop.listener import AliasedElasticPillow
import hashlib
import simplejson
from couchforms.models import XFormInstance
from django.conf import settings
from dimagi.utils.modules import to_function


UNKNOWN_VERSION = 'XXX'
UNKNOWN_UIVERSION = 'XXX'


class XFormPillow(HQPillow):
    document_class = XFormInstance
    couch_filter = "couchforms/xforms"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index_prefix = "xforms"
    es_alias = "xforms"
    es_type = "xform"
    es_index = XFORM_INDEX
    es_timeout = 60

    es_meta = {
    }

    #for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}

    #type level mapping
    default_mapping = XFORM_MAPPING

    def change_transform(self, doc_dict):
        if self.get_domain(doc_dict) is None:
            #If the domain is still None (especially when doing updates via the _changes feed)
            #skip and do nothing
            #the reason being is that changes on the xform instance do not necessarily add
            #domain to it, so we need to wait until the domain is at least populated before
            #going through with indexing this xform
            return None
        else:
            doc_ret = copy.deepcopy(doc_dict)

            if 'meta' in doc_ret['form']:
                if doc_ret['form']['meta'].get('timeEnd', None) == "":
                    doc_ret['form']['meta']['timeEnd'] = None
                if doc_ret['form']['meta'].get('timeStart', None) == "":
                    doc_ret['form']['meta']['timeStart'] = None

                # Some docs have their @xmlns and #text here
                if isinstance(doc_ret['form']['meta'].get('appVersion'), dict):
                    doc_ret['form']['meta']['appVersion'] = doc_ret['form']['meta']['appVersion'].get('#text')

            #see:  extract_case_blocks(doc_dict)
            case_blocks = extract_case_blocks(doc_ret)
            for case_dict in case_blocks:
                for date_modified_key in ['date_modified', '@date_modified']:
                    if case_dict.get(date_modified_key, None) == "":
                        case_dict[date_modified_key] = None
            return doc_ret



