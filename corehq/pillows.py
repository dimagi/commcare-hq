from auditcare.models import AuditEvent
from couchforms.models import XFormInstance
from couchlog.models import ExceptionRecord
from pillowtop.listener import NetworkPillow
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

    def change_transform(self, doc_dict):
        """
        Lighten the load of the search index by removing the data heavy transactional cruft
        """
        if doc_dict.has_key('actions'):
            del doc_dict['actions']
        if doc_dict.has_key('xform_ids'):
            del doc_dict['xform_ids']
        return doc_dict

class AuditcarePillow(NetworkPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_AUDITCARE_PORT
    couch_db = AuditEvent.get_db()
    couch_filter = 'auditcare/auditdocs'

class CouchlogPillow(NetworkPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_COUCHLOG_PORT
    couch_db = ExceptionRecord.get_db()
    couch_filter = 'couchlog/couchlogs'

class DevicelogPillow(NetworkPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_DEVICELOG_PORT
    couch_db = XFormInstance.get_db()
    couch_filter = 'couchforms/devicelogs'


class StrippedXformPillow(ElasticPillow):
    couch_db = XFormInstance.get_db()
    couch_filter = ""
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
                del doc_dict['form'][k]
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
        "settings" : {
            "analysis" : {
                "analyzer" : {
                    "lowercase_analyzer" : {
                        "type" : "custom",
                        "tokenizer" : "keyword",
                        "filter" : [ "lowercase"]}}}},
        "mappings" : {
            "domain" : {
                "properties" : {
                    "license" : { "type": "string", "index" : "not_analyzed" },
                    "deployment.region": { "type": "string", "analyzer": "lowercase_analyzer" }}}}}
