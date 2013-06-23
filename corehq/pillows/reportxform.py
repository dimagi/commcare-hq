import copy
from casexml.apps.case.xform import extract_case_blocks
from corehq.pillows.base import convert_properties
from .mappings.report_xform_mapping import REPORT_XFORM_INDEX, REPORT_XFORM_MAPPING
from .xform import XFormPillow


class ReportXFormPillow(XFormPillow):
    es_index_prefix = "report_xforms"
    es_alias = "report_xforms"
    es_type = "report_xform"
    es_index = REPORT_XFORM_INDEX

    #for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}

    #type level mapping
    default_mapping = REPORT_XFORM_MAPPING

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

            #see:  extract_case_blocks(doc_dict)
            case_blocks = extract_case_blocks(doc_ret)
            for case_dict in case_blocks:
                for date_modified_key in ['date_modified', '@date_modified']:
                    if case_dict.get(date_modified_key, None) == "":
                        case_dict[date_modified_key] = None

            #after basic transforms for stupid type mistakes are done, walk all properties.
            convert_properties(doc_ret['form'], self.default_mapping['properties']['form'], override_root_keys=['case'])
            return doc_ret



