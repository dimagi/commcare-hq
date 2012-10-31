from auditcare.models import AuditEvent
from couchforms.models import XFormInstance
from couchlog.models import ExceptionRecord
from pillowtop.listener import  LogstashMonitoringPillow
from pillowtop.listener import ElasticPillow
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
import settings


class CasePillow(ElasticPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "case/casedocs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index = "hqcases"
    es_type = "case"
    #the meta here is defined for when the case index is created for the FIRST time
    #subsequent data added to it will be added automatically, but the date_detection is necessary
    # to be false to prevent indexes from not being created due to the way we store dates
    #all will be strings EXCEPT the core case properties which we need to explicitly define below.
    #that way date sort and ranges will work with canonical date formats for queries.
    es_meta = {
        "mappings": {
            "case": {
                "date_detection": False,
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
                    }
                }
            }
        }
    }

    def change_transform(self, doc_dict):
        """
        Lighten the load of the search index by removing the data heavy transactional cruft
        """
        if doc_dict.has_key('actions'):
            #todo the actions dict is a huge amount of data whose inconsistencies cause some docs
            # not to be indexed
            del doc_dict['actions']
        if doc_dict.has_key('xform_ids'):
            #todo - xform_ids may need to be reintroduced depending on other API needs for cases
            del doc_dict['xform_ids']
        return doc_dict


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
                        "filter": ["lowercase"]}}}},
        "mappings": {
            "domain": {
                "properties": {
                    "license": {"type": "string", "index": "not_analyzed"},
                    "deployment.region": {"type": "string", "analyzer": "lowercase_analyzer"},
                    "author": {"type": "string", "analyzer": "lowercase_analyzer"}}}}}
