from __future__ import print_function
import sys
import logging
from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.db.models import signals
from requests.exceptions import RequestException
from corehq.apps.callcenter.utils import sync_user_cases, bootstrap_callcenter, get_call_center_domains
from corehq.apps.domain.models import Domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import commcare_user_post_save
from corehq.elastic import es_query, ESError

logger = logging.getLogger(__name__)

def sync_user_cases_signal(sender, **kwargs):
    return sync_user_cases(kwargs["couch_user"])

commcare_user_post_save.connect(sync_user_cases_signal)


def bootstrap_callcenter_domain_signal(sender, **kwargs):
    return bootstrap_callcenter(kwargs['domain'])


commcare_domain_post_save.connect(bootstrap_callcenter_domain_signal)


_module = __name__.rsplit('.', 1)[0]
def catch_signal(app, **kwargs):
    app_name = app.__name__.rsplit('.', 1)[0]
    if app_name == _module:
        def _log(msg):
            if not settings.DEBUG:
                logging.exception(msg)
            else:
                print(msg, file=sys.stderr)

        try:
            domains = get_call_center_domains()
        except (RequestException, ESError):
            _log('Unable to query ES for call-center domains during syncdb')
            domains = []

        for name in domains:
            domain = Domain.get_by_name(name)
            if domain:
                print('  callcenter bootstap `{0}`'.format(domain.name))
                bootstrap_callcenter(domain)

signals.post_syncdb.connect(catch_signal)
