from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import get_db

class Command(BaseCommand):
    help = "Deletes the contents of a domain"
    args = '<domain>'

    option_list = BaseCommand.option_list + (
        make_option('--simulate',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help='Don\'t delete anything, print what would be deleted.'),
    )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Usage is delete_domain %s' % self.args)

        sourcedb = get_db()
        domain = args[0].strip()
        simulate = options['simulate']

        if simulate:
            print "\nSimulated run, no data will be deleted.\n"

        domain_doc = Domain.get_by_name(domain)
        if domain_doc is None:
            # If this block not entered, domain will be deleted in delete_docs
            self.delete_domain(sourcedb, domain, simulate)


        startkey = [domain]
        endkey = [domain, {}]
        self.delete_docs(sourcedb, domain, simulate, startkey, endkey)

    def delete_domain(self, sourcedb, domain, simulate):
        result = sourcedb.view(
            "domain/domains",
            key=domain,
            reduce=False,
            include_docs=True
        ).first()

        if result and 'doc' in result:
            if not simulate:
                print "Deleting domain doc"
                domain_doc = Domain.wrap(result['doc'])
                sourcedb.delte_doc(domain_doc, empty_on_delete=True) #TODO: Attachements are deleted by this as well, right?
        else:
            print "Domain doc not found for domain %s." % domain

    def delete_docs(self, sourcedb, domain, simulate, startkey, endkey):
        # TODO: What will happen to documents in multiple domains?

        # TODO: Getting full docs instead of ids might slow things down?
        docs = [result for result in sourcedb.view("domain/docs",
                                                    startkey=startkey,
                                                    endkey=endkey,
                                                    reduce=False
                                                )]
        total = len(docs)
        print "Found %s matching documents in domain: %s" % (total, domain)

        try:
            if not simulate:
                sourcedb.delete_docs(docs, empty_on_delete=True) #TODO: Attachements are deleted by this as well, right?
                print "Deleted %s documents!" % (total,)
        except Exception, e:
            print "Delete failed! Error is: %s" % e

        #TODO: Why not just do Domain.delete()