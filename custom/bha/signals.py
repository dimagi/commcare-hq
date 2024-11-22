from django.dispatch import receiver

from corehq.form_processor.signals import sql_case_post_save
from .util import get_most_recent_referral


@receiver(sql_case_post_save, dispatch_uid="expire_bha_csql_fixtures")
def expire_bha_csql_fixtures(sender, case, **kwargs):
    # TODO see if the case is a referrals case, then clear the cache
    domain = "TODO"
    get_most_recent_referral.clear(domain)
