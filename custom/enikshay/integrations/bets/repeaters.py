from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.repeaters.models import Repeater
from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.signals import create_repeat_records
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.signals import commcare_user_post_save
from corehq.toggles import BETS_INTEGRATION


class BETSUserRepeater(Repeater):
    friendly_name = _("Forward Users")

    class Meta(object):
        app_label = 'repeaters'

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareUser.get(repeat_record.payload_id)

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def __unicode__(self):
        return "forwarding users to: %s" % self.url


@receiver(commcare_user_post_save, dispatch_uid="create_bets_user_repeat_records")
def create_user_repeat_records(sender, couch_user, **kwargs):
    create_repeat_records(BETSUserRepeater, couch_user)


class BETSLocationRepeater(Repeater):
    friendly_name = _("Forward Locations")

    class Meta(object):
        app_label = 'repeaters'

    @memoized
    def payload_doc(self, repeat_record):
        return SQLLocation.objects.get(location_id=repeat_record.payload_id)

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def __unicode__(self):
        return "forwarding locations to: %s" % self.url


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_bets_location_repeat_records")
def create_location_repeat_records(sender, raw=False, **kwargs):
    if raw:
        return

    create_repeat_records(BETSLocationRepeater, kwargs['instance'])
