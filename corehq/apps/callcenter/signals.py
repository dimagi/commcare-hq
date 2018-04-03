from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from corehq.apps.callcenter.utils import sync_call_center_user_case, sync_usercase
from corehq.apps.users.signals import commcare_user_post_save

logger = logging.getLogger(__name__)


def sync_user_cases_signal(sender, **kwargs):
    user = kwargs["couch_user"]
    sync_call_center_user_case(user)
    sync_usercase(user)

commcare_user_post_save.connect(sync_user_cases_signal)
