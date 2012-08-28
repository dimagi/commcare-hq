import restkit, couchdbkit

class PillowChange(object):
    couch_filter = None
    couch_db = None
    
    def trigger(changes_dict, db):
        """
        Step one of pillowtop process
        For a given _changes indicator, the changes dict (the _id, _rev) is sent here.
        Should return a doc_dict
        """
        return db.open_doc(changes_dict['id'), db

    def process(doc_dict, db):
        """
        process/transform doc_dict if needed.
        """
        return doc_dict
    def transport(doc_dict, db):
        """
        Finish transport of doc if needed.
        """
        pass

class ElasticPillow(object):
    """
    Elasticsearch handler
    """
    es_host = ""
    es_port = ""

    def __init__(self, es_host, es_port):
        self.es_host = es_host
        self.es_port = es_port



    def transport(doc_dict, db):
        try:
            res = Resource(self.es_host, manager=manager)
            auth_params = {'username':celeryconfig.ZPRINTER_USERNAME, 'api_key': celeryconfig.ZPRINTER_API_KEY}
            r = res.get('/api/zebra_printers/',  params_dict=auth_params)
            json = simplejson.loads(r.body_string())
            #load printers into memory, yo for caching purposes

            for printer in json['objects']:
                printer_uri = printer['resource_uri']
                printer_dict[printer_uri]=printer
                return printer_dict
        except Exception, ex:
            logging.error("Error retrieiving printers, not reachable:  %s", ex) 
            return dict()


class LogstashPillow(object):
    """
    logstash handler
    """
    ls_host = ""
    ls_port = ""


