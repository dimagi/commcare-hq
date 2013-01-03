import copy
import pdb
from corehq.pillows.case import UNKNOWN_DOMAIN, UNKNOWN_TYPE
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from pillowtop.listener import AliasedElasticPillow
import hashlib
import simplejson
from couchforms.models import XFormInstance
from pillowtop.listener import ElasticPillow
from django.conf import settings
from dimagi.utils.modules import to_function

from auditcare.utils import dict_diff


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


class XFormPillow(AliasedElasticPillow):
    couch_db = XFormInstance.get_db()
    couch_filter = "couchforms/xforms"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index_prefix = "xforms"
    es_alias = "xforms"
    es_type = "xform"

    es_meta = {
        "date_formats": DATE_FORMATS_ARR
    }
    xform_handlers = []

    #for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}

    nodomain_check = {}

    #type level mapping
    default_xform_mapping = {
        "date_detection": False,
        "date_formats": DATE_FORMATS_ARR, #for parsing the explicitly defined dates
        'ignore_malformed': True,
        'dynamic': False,
        "_meta": {
            "created": '', #record keeping on the index.
        },
        "properties": {
            "domain": {
                "type": "multi_field",
                "fields": {
                    "domain": {"type": "string", "index": "analyzed"},
                    "exact": {"type": "string", "index": "not_analyzed"}
                    #exact is full text string match - hyphens get parsed in standard
                    # analyzer
                    # in queries you can access by domain.exact
                }
            },
            "xmlns": {
                "type": "multi_field",
                "fields": {
                    "xmlns": {"type": "string", "index": "analyzed"},
                    "exact": {"type": "string", "index": "not_analyzed"}
                }
            },
            '@uiVersion': {"type": "string"},
            '@version': {"type": "string"},
            "path": {"type": "string", "index": "not_analyzed"},
            "submit_ip": {"type": "ip"},
            "app_id": {"type": "string", "index": "not_analyzed"},
            "received_on": {
                "type": "date",
                "format": DATE_FORMATS_STRING
            },
            'form': {
                'dynamic': False,
                'properties': {
                    "#type": {"type": "string", "index": "not_analyzed"},
                    'case': {
                        'dynamic': False,
                        'properties': {
                            'date_modified': {
                                "type": "date",
                                "format": DATE_FORMATS_STRING
                            },
                            '@date_modified': {
                                "type": "date",
                                "format": DATE_FORMATS_STRING
                            },

                            "@case_id": {"type": "string", "index": "not_analyzed"},
                            "@user_id": {"type": "string", "index": "not_analyzed"},
                            "@xmlns": {"type": "string", "index": "not_analyzed"},


                            "case_id": {"type": "string", "index": "not_analyzed"},
                            "user_id": {"type": "string", "index": "not_analyzed"},
                            "xmlns": {"type": "string", "index": "not_analyzed"},
                        }
                    },
                    'meta': {
                        'dynamic': False,
                        'properties': {
                            "timeStart": {
                                "type": "date",
                                "format": DATE_FORMATS_STRING
                            },
                            "timeEnd": {
                                "type": "date",
                                "format": DATE_FORMATS_STRING
                            },
                            "userID": {"type": "string", "index": "not_analyzed"},
                            "deviceID": {"type": "string", "index": "not_analyzed"},
                            "instanceID": {"type": "string", "index": "not_analyzed"},
                            "username": {"type": "string", "index": "not_analyzed"}
                        }
                    },
                },
            },
        }
    }


    def __init__(self, **kwargs):
        super(XFormPillow, self).__init__(**kwargs)

        #Pillow Handlers are custom processing classes that can add new mapping definitions beyond the
        #default/core mapping types found in self.default_xform_mapping
        #it also provides for more custom transform prior to transmission
        for full_str in getattr(settings, 'XFORM_PILLOW_HANDLERS', []):
            func = to_function(full_str)
            self.xform_handlers.append(func())
        self.handler_domain_map = dict((x.domain, x) for x in self.xform_handlers)

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        if not hasattr(self, '_calc_meta'):
            self._calc_meta = hashlib.md5(simplejson.dumps(
                self.get_mapping_from_type({'_id': 'default', 'domain': 'default', 'type': 'default'}))).hexdigest()
        return self._calc_meta

    def get_domain(self, doc_dict):
        domain = doc_dict.get('domain', None)

        if domain is None:
            if not self.nodomain_check.has_key(doc_dict['_id']):
                #if there's no domain, then this instance doesn't have all the signals/post processing done, skip and wait
                self.nodomain_check[doc_dict['_id']] = 0
            self.nodomain_check[doc_dict['_id']] += 1
            return None
        else:
            if self.nodomain_check.has_key(doc_dict['_id']):
                pass
            return domain

    def get_type_string(self, doc_dict):
        domain = self.get_domain(doc_dict)
        if domain is None:
            domain = UNKNOWN_DOMAIN

        ui_version = doc_dict.get('form', {}).get('@uiVersion', 'XXX')
        version = doc_dict.get('form', {}).get('@version', 'XXX')
        xmlns = doc_dict.get('xmlns', 'http://%s' % UNKNOWN_TYPE )
        if xmlns is None:
            xmlns_str = UNKNOWN_TYPE
        else:
            xmlns_str = xmlns.split('/')[-1]
        ret =  "%(type)s_%(domain)s_%(xmlns_suffix)s_u%(ui_version)s_v%(version)s" % {
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
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but the date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all will be strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.

        mapping = self.default_xform_mapping
        if doc_dict.get('domain', None) is not None:
            if self.handler_domain_map.has_key(doc_dict['domain']):
                if self.handler_domain_map[doc_dict['domain']].has_custom_mapping(doc_dict):
                    mapping = self.handler_domain_map[doc_dict['domain']].get_custom_mapping(doc_dict, mapping=mapping)

        return {
            self.get_type_string(doc_dict): mapping
        }

    def change_transform(self, doc_dict):
        if self.get_domain(doc_dict) is None:
            return None
        else:
            doc_ret = dict.copy(doc_dict)
            #print simplejson.dumps(doc_dict) == simplejson.dumps(doc_ret)
#            removed, added, changed = dict_diff(doc_ret, doc_dict)
            # universal xform handler for timeStart
            # to address a touchforms issue
            if doc_ret['form'].has_key('meta'):
                if doc_ret['form']['meta'].get('timeEnd', None) == "":
                    doc_ret['form']['meta']['timeEnd'] = None
                if doc_ret['form']['meta'].get('timeStart', None) == "":
                    doc_ret['form']['meta']['timeStart'] = None

            if self.handler_domain_map.has_key(doc_ret['domain']):
                doc_ret = self.handler_domain_map[doc_ret['domain']].handle_transform(doc_ret)
            return doc_ret



