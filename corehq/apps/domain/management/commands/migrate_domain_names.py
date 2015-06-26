from dimagi.ext.couchdbkit import Document
from django.core.management.base import LabelCommand, CommandError
from corehq.apps.domain.models import OldDomain
from corehq.apps.domain.shortcuts import create_domain, create_user
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.users.models import CouchUser
from dimagi.utils.couch.database import get_db

class Command(LabelCommand):
     
    def handle(self, *args, **options):
        django_domains = OldDomain.objects.all()
        django_domain_names = set([domain.name for domain in django_domains])
        couch_domain_names = set([x['key'][0] for x in get_db().view('domain/docs', group_level=1).all()])
        couch_user_domain_names = set([x['key'] for x in get_db().view('users/by_domain', group=True).all()])
        print get_db().view('users/by_domain').all()
        normalized_names = {}
        domains_that_need_to_change = set()


        # print some warnings if things are fishy
        for domain in couch_domain_names.union(couch_user_domain_names):
            if domain not in django_domain_names:
                print "Warning: domain '%s' not in SQL" % domain

            normalized = normalize_domain_name(domain)
            if normalized in normalized_names:
                print "Warning: domains '%s' and '%s' both exist" % (domain, normalized_names[normalized])
            normalized_names[normalized] = domain
            if normalized != domain:
                domains_that_need_to_change.add(domain)

        print "Going to change the following domains:"
        for domain in domains_that_need_to_change:
            print "    %s" % domain
        print
        if raw_input("Are you sure you want to continue? (Y/n)") != 'Y':
            print "Mission aborted"
            return

        print "Migrating SQL domains"
        for django_domain in django_domains:
            django_domain.name = normalize_domain_name(django_domain.name)
            django_domain.save()

        print "Migrating domains in Couch docs"
        class MyDoc(Document):
            class Meta:
                app_label = 'domain'
        def get_docs(domain):
            chunk_size = 500
            i = 0
            while True:
                docs = MyDoc.view('domain/docs',
                                  startkey=[domain], endkey=[domain, {}],
                                  reduce=False, include_docs=True, skip=i*chunk_size, limit=chunk_size)
                for doc in docs:
                    yield doc
                if not len(docs):
                    break
                i += 1
        for domain in domains_that_need_to_change:
            print "%s:" % domain
            for doc in get_docs(domain):
                print '.',
                if 'domain' in doc:
                    doc['domain'] = normalize_domain_name(doc['domain'])
                if 'domains' in doc:
                    for i,domain in enumerate(doc['domains']):
                        doc['domains'][i] = normalize_domain_name(doc['domains'][i])
                doc.save()
            print

        print "Patching users"
        for domain in domains_that_need_to_change:
            print '.',
            couch_users = CouchUser.view('users/by_domain', key=domain, include_docs=True, reduce=False)
            for user in couch_users:
                for dm in user.web_account.domain_memberships:
                    dm.domain = normalize_domain_name(dm.domain)
                for account in user.commcare_accounts:
                    if account.domain:
                        account.domain = normalize_domain_name(account.domain)
                user.save()
