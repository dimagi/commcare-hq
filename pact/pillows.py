import logging
from django.conf import settings
import gevent
from casexml.apps.case.models import CommCareCase
from corehq.pillows import dynamic
from pact.enums import PACT_SCHEDULES_NAMESPACE
from pact.models import CDotWeeklySchedule
from pillowtop.listener import ElasticPillow, WAIT_HEARTBEAT


def schedule_mapping_generator():
    m = dynamic.DEFAULT_MAPPING_WRAPPER
    doc_class=CDotWeeklySchedule
    m['properties'] = dynamic.set_properties(doc_class)
    m['_meta']['created'] = "foo"
    return m

class PactCaseSchedulePillow(ElasticPillow):
    couch_db = CommCareCase.get_db()
    couch_filter = "case/casedocs_by_domain"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_index = "domain_typed_data"
    es_type = "pact_schedule"
    es_meta = {}

    def __init__(self, **kwargs):
        super(PactCaseSchedulePillow, self).__init__(**kwargs)
        mapping = self.get_index_mapping()
        if not mapping.has_key(self.es_type):
#            print "setting maping: %s" % self.es_type
#            print schedule_mapping_generator()
            print self.set_mapping(self.es_type, {self.es_type: schedule_mapping_generator()})
#            logging.info("Pillowtop [%s] Retrieved mapping from ES" % self.get_name())

    def old_changes(self):
        from couchdbkit import  Consumer
        c = Consumer(self.couch_db, backend='gevent')
        while True:
            try:
                c.wait(self.parsing_processor, since=self.since, filter=self.couch_filter,
                       heartbeat=WAIT_HEARTBEAT, feed='continuous', timeout=30000, domain="pact")
            except Exception, ex:
                logging.exception("Exception in form listener: %s, sleeping and restarting" % ex)
                gevent.sleep(5)


    def change_transport(self, doc_dict):
        """
        Default elastic pillow for a given doc to a type.
        """
        try:
            es = self.get_es()
            #explode the schedule
            computed = doc_dict.get('computed_', {})
            if computed.has_key(PACT_SCHEDULES_NAMESPACE):
                print "in computed"
                for sched in computed[PACT_SCHEDULES_NAMESPACE]:
                    print "\tcase_id: %s: %s" % (doc_dict['_id'], sched['schedule_id'])
                    doc_id = sched['schedule_id']
                    sched['_id'] = doc_id
                    sched['case_id'] = doc_dict['_id']
                    sched['domain'] = 'pact'
                    del sched['schedule_id']
                    doc_path = self.get_doc_path(doc_id)
                    if self.allow_updates:
                        can_put = True
                    else:
                        can_put = not self.doc_exists(doc_id)

                    if can_put:
                        res = es.put(doc_path,  data = sched)
                        if res.get('status', 0) == 400:
                            logging.error("Pillowtop Error [%s]:\n%s\n\tDoc id: %s\n" % (self.get_name(),
                                                                                             res.get('error', "No error message"),
                                                                                             doc_dict['_id']))
        except Exception, ex:
            logging.error("PillowTop [%s]: transporting change data to elasticsearch error: %s",
                          (self.get_name(), ex))
            return None

