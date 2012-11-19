from casexml.apps.case.models import CommCareCase
from pillowtop.listener import AliasedElasticPillow
import hashlib
import simplejson
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

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but the date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all will be strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): {
                "date_detection": False,
                "_meta": {
                    "created": '',
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
                type_mapping[self.get_type_string(doc_dict)]['_meta'][
                'created'] = datetime.isoformat(datetime.utcnow())
                es.put("%s/%s/_mapping" % (self.es_index, self.get_type_string(doc_dict)),
                    data=type_mapping)
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
            logging.error(
                "PillowTop [%s]: transporting change data doc_id: %s to elasticsearch error: %s",
                (self.get_name(), doc_dict['_id'], ex))
            return None