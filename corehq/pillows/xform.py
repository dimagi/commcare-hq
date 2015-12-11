import collections
import copy
from casexml.apps.case.xform import extract_case_blocks, get_case_ids_from_form
from corehq.pillows.mappings.xform_mapping import XFORM_MAPPING, XFORM_INDEX
from .base import HQPillow
from couchforms.const import RESERVED_WORDS
from couchforms.models import XFormInstance
from dateutil import parser


UNKNOWN_VERSION = 'XXX'
UNKNOWN_UIVERSION = 'XXX'

def is_valid_date(txt):
    try:
        if txt and parser.parse(txt):
            return True
    except Exception:
        pass
    return False

RESERVED = RESERVED_WORDS[:]
RESERVED.remove('case')

# modified from: http://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
def flatten(d, parent_key='', delimiter='/'):
    items = []
    for k, v in d.items():
        if k in RESERVED:
            continue
        new_key = parent_key + delimiter + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, delimiter).items())
        else:
            items.append((new_key, v))
    return dict(items)


class XFormPillow(HQPillow):
    document_class = XFormInstance
    couch_filter = "couchforms/xforms"
    es_alias = "xforms"
    es_type = "xform"
    es_index = XFORM_INDEX
    include_docs = False

    # for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}
    default_mapping = XFORM_MAPPING

    @classmethod
    def get_unique_id(self):
        return XFORM_INDEX

    def change_transform(self, doc_dict, include_props=True):
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
                if not is_valid_date(doc_ret['form']['meta'].get('timeEnd', None)):
                    doc_ret['form']['meta']['timeEnd'] = None
                if not is_valid_date(doc_ret['form']['meta'].get('timeStart', None)):
                    doc_ret['form']['meta']['timeStart'] = None

                # Some docs have their @xmlns and #text here
                if isinstance(doc_ret['form']['meta'].get('appVersion'), dict):
                    doc_ret['form']['meta']['appVersion'] = doc_ret['form']['meta']['appVersion'].get('#text')

            case_blocks = extract_case_blocks(doc_ret)
            for case_dict in case_blocks:
                for date_modified_key in ['date_modified', '@date_modified']:
                    if not is_valid_date(case_dict.get(date_modified_key, None)):
                        if case_dict.get(date_modified_key) == '':
                            case_dict[date_modified_key] = None
                        else:
                            case_dict.pop(date_modified_key, None)

                # convert all mapped dict properties to nulls if they are empty strings
                for object_key in ['index', 'attachment', 'create', 'update']:
                    if object_key in case_dict and not isinstance(case_dict[object_key], dict):
                        case_dict[object_key] = None

            doc_ret["__retrieved_case_ids"] = list(get_case_ids_from_form(doc_dict))
            if include_props:
                form_props = ["%s:%s" % (k, v) for k, v in flatten(doc_ret['form']).iteritems()]
                doc_ret["__props_for_querying"] = form_props
            return doc_ret



