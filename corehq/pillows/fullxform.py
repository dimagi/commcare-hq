from django.conf import settings
from corehq.pillows.mappings.fullxform_mapping import FULL_XFORM_INDEX

from corehq.pillows.xform import XFormPillow
from corehq.pillows.case import UNKNOWN_DOMAIN, UNKNOWN_TYPE
from corehq.pillows.xform import UNKNOWN_VERSION, UNKNOWN_UIVERSION
from dimagi.utils.modules import to_function


class XFormPillowHandler(object):
    """
    Special handler for xforms. The goal is to keep all xforms in the same index until otherwise.
    There are places where an xform prior to being sent to ES needs to be handled due to quirks
    in the data and how it would interact with ES. This handler allows for a registry of specific
     cases.
    """

    domain = ""

    def has_custom_mapping(self, doc_dict, **kwargs):
        return False

    def get_custom_mapping(self, doc_dict, **kwargs):
        pass

    def handle_transform(self, doc_dict, **kwargs):
        return doc_dict


class FullXFormPillow(XFormPillow):
    es_index_prefix = "full_xforms"
    es_alias = "full_xforms"
    es_type = "fullxform"
    es_index = FULL_XFORM_INDEX

    xform_handlers = []

    #for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}

    def __init__(self, **kwargs):
        super(FullXFormPillow, self).__init__(**kwargs)

        self.handler_domain_map = self.load_domains()
        self.xform_handlers = self.handler_domain_map.values()

    @staticmethod
    def load_domains():
        #Pillow Handlers are custom processing classes that can add new mapping definitions
        # beyond the default/core mapping types found in self.default_xform_mapping
        #it also provides for more custom transform prior to transmission
        def custom_domains():
            for full_str in getattr(settings, 'XFORM_PILLOW_HANDLERS', []):
                func = to_function(full_str)
                yield func()
        handler_mapping = dict((x.domain, x) for x in custom_domains())

        # full xforms-indexed domains that don't require custom processing
        noncustom_domains = getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])
        handler_mapping.update((domain, XFormPillowHandler()) for domain in noncustom_domains)
        
        return handler_mapping

    def get_type_string(self, doc_dict):
        domain = self.get_domain(doc_dict)
        if domain is None:
            domain = UNKNOWN_DOMAIN

        ui_version = doc_dict.get('form', {}).get('@uiVersion', UNKNOWN_UIVERSION)
        version = doc_dict.get('form', {}).get('@version', UNKNOWN_VERSION)
        xmlns = doc_dict.get('xmlns', 'http://%s' % UNKNOWN_TYPE )
        if xmlns is None:
            xmlns_str = UNKNOWN_TYPE
        else:
            xmlns_str = xmlns.split('/')[-1]
        ret = "%(type)s_%(domain)s_%(xmlns_suffix)s_u%(ui_version)s_v%(version)s" % {
            'type': self.es_type,
            'domain': domain.lower(),
            'xmlns_suffix': xmlns_str,
            'ui_version': ui_version,
            'version': version
        }
        return ret

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the domain_type document.
        """
        mapping = self.default_xform_mapping
        if doc_dict.get('domain', None) is not None:
            if doc_dict['domain'] in self.handler_domain_map:
                if self.handler_domain_map[doc_dict['domain']].has_custom_mapping(doc_dict):
                    mapping = self.handler_domain_map[doc_dict['domain']].get_custom_mapping(doc_dict, mapping=mapping)

        return {
            self.get_type_string(doc_dict): mapping
        }

    def change_transform(self, doc_dict):
        doc_ret = super(FullXFormPillow, self).change_transform(doc_dict)
        if doc_ret is not None:
            if doc_ret['domain'] in self.handler_domain_map:
                doc_ret = self.handler_domain_map[doc_ret['domain']].handle_transform(doc_ret)
            else:
                #it's not in our custom handlers. return None
                doc_ret = None
        return doc_ret

