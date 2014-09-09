from django.db.models import Q
from corehq.apps.smsbillables.models import SmsBillable
from django.core.management.base import LabelCommand
from corehq.apps.sms.models import SMSLog


class Command(LabelCommand):
    help = ("Make sure domain is filled in for SMSBillable where domain is "
            "None. This retro-fixes an issue where domains weren't stored "
            "in the billable during its creation. September 2014.")
    args = ""
    label = ""

    def handle(self, *args, **options):
        missing_domain_billables = SmsBillable.objects.filter(
            Q(domain=u'') | Q(domain=None)
        )
        for billable in missing_domain_billables:
            msg_log = SMSLog.get(billable.log_id)
            billable.domain = msg_log.domain
            if billable.domain:
                billable.save()
                print "Updated Billable from %s for domain %s" % (
                    billable.date_created, billable.domain
                )
            else:
                print "could not find a domain in SMSLog %s." % billable.log_id
