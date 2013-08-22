import copy
from casexml.apps.case.xform import extract_case_blocks
from corehq.pillows.base import convert_properties
from corehq.pillows.fullxform import XFormPillowHandler
from dimagi.utils.modules import to_function
from .mappings.reportxform_mapping import REPORT_XFORM_INDEX, REPORT_XFORM_MAPPING
from .xform import XFormPillow
from django.conf import settings


class ReportXFormPillow(XFormPillow):
    """
    an extension to XFormPillow that provides for indexing of arbitrary data fields
    within the xform

    NOTE: supersedes FullXFormPillow
    """
    es_index_prefix = "report_xforms"
    es_alias = "report_xforms"
    es_type = "report_xform"
    es_index = REPORT_XFORM_INDEX

    #type level mapping
    default_mapping = REPORT_XFORM_MAPPING


    @staticmethod
    def load_domains():
        #Pillow Handlers are custom processing classes that can add new mapping definitions
        # beyond the default/core mapping types found in self.default_mapping
        #it also provides for more custom transform prior to transmission
        handler_mapping = dict()

        # get predefined domains to map full into report xforms
        report_domains = getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])
        handler_mapping.update((domain, XFormPillowHandler()) for domain in report_domains)

        return handler_mapping


    def change_transform(self, doc_dict):
        domain = self.get_domain(doc_dict)

        if domain is None:
            #If the domain is still None (especially when doing updates via the _changes feed)
            #skip and do nothing
            #the reason being is that changes on the xform instance do not necessarily add
            #domain to it, so we need to wait until the domain is at least populated before
            #going through with indexing this xform
            return None

        if domain not in getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', []):
            #full indexing is only enabled for select domains on an opt-in basis
            return None

        doc_ret = copy.deepcopy(doc_dict)

        if 'meta' in doc_ret['form']:
            if doc_ret['form']['meta'].get('timeEnd', None) == "":
                doc_ret['form']['meta']['timeEnd'] = None
            if doc_ret['form']['meta'].get('timeStart', None) == "":
                doc_ret['form']['meta']['timeStart'] = None

        case_blocks = extract_case_blocks(doc_ret)
        for case_dict in case_blocks:
            for date_modified_key in ['date_modified', '@date_modified']:
                if case_dict.get(date_modified_key, None) == "":
                    case_dict[date_modified_key] = None

        #after basic transforms for stupid type mistakes are done, walk all properties.
        convert_properties(doc_ret['form'], self.default_mapping['properties']['form'], override_root_keys=['case'])
        return doc_ret



