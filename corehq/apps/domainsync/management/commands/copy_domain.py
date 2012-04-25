from django.core.management.base import LabelCommand, CommandError
from dimagi.utils.couch.database import get_db
from corehq.apps.domainsync.config import DocumentTransform, save
from couchdbkit.client import Database

class Command(LabelCommand):
    help = "Copies the contents of a domain to another database."
    args = '<sourcedb> <domain>'
    label = ""
     
    def handle(self, *args, **options):
        
        if len(args) != 2:
            raise CommandError('Usage is copy_domain %s' % self.args)
        
        sourcedb = Database(args[0])
        domain = args[1].strip()
        
        all_docs = sourcedb.view("domain/docs", startkey=[domain], 
                                 endkey=[domain, {}], reduce=False)
        
        total = len(all_docs)
        count = 0
        targetdb = get_db()
        print "found %s matching documents in domain: %s" % (total, domain)
        for row in all_docs:
            try:
                count += 1
                dt = DocumentTransform(sourcedb.get(row["id"]), sourcedb)
                save(dt, targetdb)
                print "Synced %s/%s docs (%s: %s)" % (count, total, row["key"][1], row["id"])
            except Exception, e:
                print "Document %s failed! Error is: %s" % (row["id"], e)
            
        