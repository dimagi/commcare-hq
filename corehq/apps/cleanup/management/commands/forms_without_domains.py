from optparse import make_option
from django.core.management.base import BaseCommand, LabelCommand
from casexml.apps.case.util import reprocess_form_cases
from corehq.apps.cleanup.xforms import guess_domain
from couchforms.models import XFormInstance


class Command(BaseCommand):
    args = '<id>'
    help = ('Find forms without domains.')
    option_list = LabelCommand.option_list + \
        (make_option('--cleanup', action='store_true', dest='cleanup', default=False,
            help="Cleanup any forms matched to a single domain by reprocessing them."),)


    def handle(self, *args, **options):
        forms = all_forms_without_domains()
        headers = ['id','xmlns','username','received_on','domain','# matched domains']
        if not options["cleanup"]:
            print ','.join(headers)
        for f in forms:
            domains = guess_domain(f)
            domain = domains[0] if domains else ''
            if not options["cleanup"]:
                print ",".join([f._id, f.xmlns or '', f.metadata.username or '', f.received_on.isoformat(), domain, str(len(domains))])
            else:
                if len(domains) == 1:
                    f.domain = domain
                    reprocess_form_cases(f)
                    print 'added form %s to domain %s' % (f._id, domains[0])
                else:
                    print 'form %s failed because there were %s matching domains: %s' % (f._id, len(domains), ', '.join(domains))


def all_forms_without_domains():
    return XFormInstance.view(
        'reports_forms/all_forms',
        reduce=False,
        startkey=['completion', None],
        endkey=["completion", None, {}],
        include_docs=True,
    )

