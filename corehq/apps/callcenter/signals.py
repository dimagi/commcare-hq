from __future__ import print_function
import sys
import logging
from django.conf import settings
from django.db.models import signals
from requests.exceptions import RequestException
from corehq.apps.callcenter.utils import sync_user_cases, bootstrap_callcenter
from corehq.apps.domain.models import Domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import commcare_user_post_save

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
        from corehq.apps.appstore.views import es_query

        try:
            q = {'fields': ['name']}
            result = es_query(params={
                'internal.using_call_center': True,
                'is_active': True,
                'is_snapshot': False
            }, q=q)
            hits = result.get('hits', {}).get('hits', {})
            for hit in hits:
                domain = Domain.get(hit['_id'])
                print('  callcenter bootstap `{0}`'.format(domain.name))
                bootstrap_callcenter(domain)
        except RequestException:
            if not settings.DEBUG:
                logging.exception('Unable to query ES for call-center domains during syncdb')
            else:
                print('WARNING: unable to query ES for call-center domains', file=sys.stderr)


signals.post_syncdb.connect(catch_signal)
