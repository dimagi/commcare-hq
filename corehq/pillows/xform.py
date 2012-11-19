import pdb
import traceback
from corehq.pillows.core import date_format_arr, formats_string
import sys
from pillowtop.listener import AliasedElasticPillow
import hashlib
import simplejson
from couchforms.models import XFormInstance
from pillowtop.listener import ElasticPillow
import logging
from django.conf import settings
from datetime import datetime


class StrippedXformPillow(ElasticPillow):
    couch_db = XFormInstance.get_db()
    couch_filter = "couchforms/xforms"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index = "xforms_clean"
    es_type = "xform"

    def change_transform(self, doc_dict):
        """
        strip all properties of the form except meta/submit info
        """
        for k in doc_dict['form']:
            if k not in ['meta', 'Meta', '@uiVersion', '@version']:
                try:
                    del doc_dict['form'][k]
                except:
                    pass
                    #todo: add geoip block here
        return doc_dict

    def change_transport(self, doc_dict):
        #not ready yet!
        return None


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

    seen_types = {}
    es_meta = {
        "date_formats": date_format_arr
    }
    xform_handlers = []

    #for simplicity, the handlers are managed on the domain level
    handler_domain_map = {}

    #type level mapping
    default_xform_mapping = {
        "date_detection": False,
        "date_formats": date_format_arr, #for parsing the explicitly defined dates
        'ignore_malformed': True,
        "_meta": {
            "created": '', #record keeping on the index.
        },
        "properties": {
            "xmlns": {
                "type": "multi_field",
                "fields": {
                    "xmlns": {"type": "string", "index": "analyzed"},
                    "exact": {"type": "string", "index": "not_analyzed"}
                }
            },
            "path": {"type": "string", "index": "not_analyzed"},
            "submit_ip": {"type": "ip"},
            "app_id": {"type": "string", "index": "not_analyzed"},
            "received_on": {
                "type": "date",
                "format": formats_string
            },
            'form': {
                'properties': {
                    'case': {
                        'properties': {
                            'date_modified': {
                                "type": "date",
                                "format": formats_string
                            },
                            '@date_modified': {
                                "type": "date",
                                "format": formats_string
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
                        'properties': {
                            "timeStart": {
                                "type": "date",
                                "format": formats_string
                            },
                            "timeEnd": {
                                "type": "date",
                                "format": formats_string
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

        for full_str in getattr(settings,'XFORM_PILLOW_HANDLERS', []):
            comps = full_str.split('.')
            handler_class_str = comps[-1]
            mod_str = '.'.join(comps[0:-1])
            mod = __import__(mod_str, {},{},[handler_class_str])
            if hasattr(mod, handler_class_str):
                handler_class  = getattr(mod, handler_class_str)
                self.xform_handlers.append(handler_class())
        self.handler_domain_map = dict((x.domain, x) for x in self.xform_handlers)

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        if not hasattr(self, '_calc_meta'):
            self._calc_meta = hashlib.md5(simplejson.dumps(
                self.get_mapping_from_type({'domain': 'default', 'type': 'default'}))).hexdigest()
        return self._calc_meta

    def get_type_string(self, doc_dict):
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = "nodomain"
        ui_version = doc_dict.get('form', {}).get('@uiVersion', 'XXX')
        version = doc_dict.get('form', {}).get('@version', 'XXX')
        xmlns = doc_dict.get('xmlns', 'http://noxmlns')
        return "%(type)s.%(domain)s.%(xmlns_suffix)s.u%(ui_version)s-v%(version)s" % {
            'type': self.es_type,
            'domain': domain.lower(),
            'xmlns_suffix': xmlns.split('/')[-1],
            'ui_version': ui_version,
            'version': version
        }

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
                    print "has custom mapping"
                    mapping = self.handler_domain_map[doc_dict['domain']].get_custom_mapping(doc_dict, mapping=mapping)

        return {
            self.get_type_string(doc_dict): mapping
        }


    def change_transport(self, doc_dict):
        """
        Override the elastic transport to go to the index + the type being a string between the
        domain and case type
        """
        try:
            es = self.get_es()

            if not self.type_exists(doc_dict):
                #if type is never seen, apply mapping for said type
                type_mapping = self.get_mapping_from_type(doc_dict)
                type_mapping[self.get_type_string(doc_dict)]['_meta']['created'] = datetime.isoformat(datetime.utcnow())
                mapping_res = es.put("%s/%s/_mapping" % (self.es_index, self.get_type_string(doc_dict)), data=type_mapping)
                print mapping_res
                #this server confirm is a modest overhead but it tells us whether or not the type
                # is successfully mapped into the index.
                #0.19 mapping - retrieve the mapping to confirm that it's been seen
                #print "Setting mapping for: %s" % self.get_type_string(doc_dict)
                self.seen_types = es.get('%s/_mapping' % self.es_index)[self.es_index]

            doc_path = self.get_doc_path_typed(doc_dict)

            if self.allow_updates:
                can_put = True
            else:
                can_put = not self.doc_exists(doc_dict['_id'])

            if can_put:
                #final check, check the handlers
                if doc_dict.get('domain', None) is not None:
                    if self.handler_domain_map.has_key(doc_dict['domain']):
                        doc_dict = self.handler_domain_map[doc_dict['domain']].handle_transform(doc_dict)

                res = es.put(doc_path, data=doc_dict)
                if res.get('status', 0) == 400:
                    print "xform error: %s\n%s" % (doc_dict['_id'], simplejson.dumps(res, indent=4))
                    #                    logging.error("Pillowtop Error [%s]:\n%s\n\tDoc id: %s\n\t%s" % (self.get_name(),
                    #                                                                           res.get('error',
                    #                                                                               "No error message"),
                    #                                                                           doc_dict['_id'],
                    #                                                                           doc_dict.keys()))
        except Exception, ex:
            print 'xforms [%s] error: %s' % (doc_dict['_id'], ex)
            traceback.print_exc(file=sys.stdout)
#            logging.error("PillowTop [%s]: transporting change data doc_id: %s to elasticsearch error: %s", (self.get_name(), doc_dict['_id'], ex))
            return None