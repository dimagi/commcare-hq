import hashlib
import simplejson
from auditcare.models import AuditEvent
from couchforms.models import XFormInstance
from couchlog.models import ExceptionRecord
from pillowtop.listener import  LogstashMonitoringPillow, AliasedElasticPillow
from pillowtop.listener import ElasticPillow
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
import logging
import settings
from datetime import datetime


class CasePillow(AliasedElasticPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "case/casedocs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index_prefix = "hqcases"
    es_alias = "hqcases"
    es_type = "case"

    seen_types = {}

    es_meta = {}

    def calc_meta(self):
        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determind md5
        """
        if not hasattr(self, '_calc_meta'):
            self._calc_meta = hashlib.md5(simplejson.dumps(
                self.get_mapping_from_type({'domain': 'default', 'type': 'default'}))).hexdigest()
        return self._calc_meta

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the domain_type document.
        See below on why date_detection is False
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but the date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all will be strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): {
                "date_detection": False,
                "_meta" : {
                    "created" : '',
                },
                "properties": {
                    "name": {
                        "type": "string"
                    },
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
                    "modified_on": {
                        "format": "dateOptionalTime",
                        "type": "date"
                    },
                    "closed_on": {
                        "format": "dateOptionalTime",
                        "type": "date"
                    },
                    "opened_on": {
                        "format": "dateOptionalTime",
                        "type": "date"
                    },
                    "server_modified_on": {
                        "type": "date",
                        "format": "dateOptionalTime"
                    },
                    "user_id": {
                        "type": "string"
                    },
                    "closed": {
                        "type": "boolean"
                    },
                    "type": {
                        "type": "string"
                    },
                    "owner_id": {
                        "type": "string"
                    },
                    "xform_ids": {"type": "string", "index_name": "xform_id"},
                    'actions': {
                        'properties': {
                            'action_type': {
                                "type": "string"
                            },
                            'seq': {
                                'type': 'long'
                            },
                            'server_date': {
                                "format": "dateOptionalTime",
                                "type": "date"
                            },
                            'date': {
                                "format": "dateOptionalTime",
                                "type": "date"
                            },
                            'xform_id': {
                                "type": "string"
                            },
                        }
                    }
                }
            }
        }


    def get_type_string(self, doc_dict):
        domain = doc_dict.get('domain', None)
        if domain is None:
            domain = "unknowndomain"
        case_type = doc_dict.get('type', None)
        if case_type is None:
            case_type = "unknowntype"

        return "%(type)s_%(domain)s__%(case_type)s" % {
            'type': self.es_type,
            'domain': domain.lower(),
            'case_type': case_type.lower(),
        }

    def get_doc_path_typed(self, doc_dict):
        return "%(index)s/%(type_string)s/%(id)s" % (
            {
                'index': self.es_index,
                'type_string': self.get_type_string(doc_dict),
                'id': doc_dict['_id']
            })

    def type_exists(self, doc_dict):
        es = self.get_es()

        type_string = self.get_type_string(doc_dict)

        ##################
        #ES 0.20 has the index HEAD API.  While we're on 0.19, we will need to poll the index
        # metadata
        #type_path = "%(index)s/%(type_string)s" % ( { 'index': self.es_index, 'type_string': type_string, })

        #if we don't want to server confirm it for both .19 or .20, then this hash is enough
        #if self.seen_types.has_key(type_string):
            #return True
        #else:
            #self.seen_types[type_string] = True
        #head_result = es.head(type_path)
        #return head_result
        ##################

        #####
        #0.19 method, get the mapping from the index
        return self.seen_types.has_key(type_string)

    def doc_exists(self, doc_dict):
        """
        Overrided based upon the doc type
        """
        es = self.get_es()
        doc_path = "%(index)s/%(type)s_%(domain)s__%(case_type)s/%(id)s" % (
            {
                'index': self.es_index,
                'type': self.es_type,
                'domain': doc_dict.get('domain', 'unknowndomain'),
                'case_type': doc_dict.get('type', 'unknowntype'),
                'id': doc_dict['_id']
            })
        head_result = es.head(doc_path)
        return head_result


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
                #update metadata
                type_mapping[self.get_type_string(doc_dict)]['_meta']['created'] = datetime.isoformat(datetime.utcnow())
                es.put("%s/%s/_mapping" % (self.es_index, self.get_type_string(doc_dict)), data=type_mapping)
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
                res = es.put(doc_path, data=doc_dict)
                if res.get('status', 0) == 400:
                    logging.error(
                        "Pillowtop Error [%s]:\n%s\n\tDoc id: %s\n\t%s" % (self.get_name(),
                                                                           res.get('error',
                                                                               "No error message"),
                                                                           doc_dict['_id'],
                                                                           doc_dict.keys()))
        except Exception, ex:
            logging.error("PillowTop [%s]: transporting change data doc_id: %s to elasticsearch error: %s",
                (self.get_name(), doc_dict['_id'], ex))
            return None


class AuditcarePillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_AUDITCARE_PORT
    couch_db = AuditEvent.get_db()
    couch_filter = 'auditcare/auditdocs'


class CouchlogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_COUCHLOG_PORT
    couch_db = ExceptionRecord.get_db()
    couch_filter = 'couchlog/couchlogs'


class DevicelogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_DEVICELOG_PORT
    couch_db = XFormInstance.get_db()
    couch_filter = 'couchforms/devicelogs'


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


class ExchangePillow(ElasticPillow):
    couch_db = Domain.get_db()
    couch_filter = "domain/all_domains"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index = "cc_exchange"
    es_type = "domain"
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "lowercase_analyzer": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["lowercase"]},
                    "comma":{
                        "type": "pattern",
                        "pattern":","}}}},
        "mappings": {
            "domain": {
                "properties": {
                    "license": {"type": "string", "index": "not_analyzed"},
                    "deployment.region": {"type": "string", "analyzer": "lowercase_analyzer"},
                    "author": {"type": "string", "analyzer": "lowercase_analyzer"},
                    "project_type": {"type": "string", "analyzer": "comma"}}}}}