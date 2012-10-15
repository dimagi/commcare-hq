import logging
from couchdbkit.changes import ChangesStream
import restkit, couchdbkit
from restkit.resource import Resource
import simplejson
from gevent import socket

class BasicPillow(object):
    couch_filter = None # string for filter if needed
    couch_db = None #couchdbkit Database Object

    def run(self, since=0):
        """
        Couch changes stream creation
        """
        print "Starting pillow %s" % self.__class__
        with ChangesStream(self.couch_db, feed='continuous', heartbeat=True, since=since) as st:
            for c in st:
                self.processor(c)

    def processor(self, change):
        t = self.change_trigger(change)
        if t is not None:
            tr = self.change_transform(t)
            if tr is not None:
                self.change_transport(tr)


    def change_trigger(self, changes_dict):
        """
        Step one of pillowtop process
        For a given _changes indicator, the changes dict (the _id, _rev) is sent here.
        Should return a doc_dict
        """
        #return self.couch_db.open_doc(changes_dict['id'])
        return changes_dict

    def change_transform(self, doc_dict):
        """
        process/transform doc_dict if needed.
        """
        return doc_dict
    def change_transport(self, doc_dict):
        """
        Finish transport of doc if needed.
        """
        pass

class ElasticPillow(BasicPillow):
    """
    Elasticsearch handler
    """
    es_host = ""
    es_port = ""
    es_index = ""

    def change_transport(doc_dict):
        try:
            res = Resource("%s:%s" % (self.es_host, self.es_port))
            r = res.post(self.es_index, payload = simplejson.dumps(doc_dict))
            return r.status
        except Exception, ex:
            logging.error("PillowTop: transporting change data to eleasticsearch error:  %s", ex)
            return None


class NetworkPillow(BasicPillow):
    """
    Basic network endpoint handler.
    This is useful for the logstash/Splunk use cases.
    """
    endpoint_host = ""
    endpoint_port = 0
    transport_type = 'tcp'

    def change_transport(self, doc_dict):
        print "Change Transport %s: %s" % (self.__class__, doc_dict)
        return
        try:
            address = (self.endpoint_host, self.endpoint_port)
            if self.transport_type == 'tcp':
               stype = socket.SOCK_STREAM
            elif self.transport_type == 'udp':
                stype = socket.SOCK_DGRAM
            sock = socket.socket(type=stype)
            sock.connect(address)
            sock.send(simplejson.dumps(doc_dict))
            return 1
        except Exception, ex:
            logging.error("PillowTop: transport to network socket error: %s" % ex)
            return None

