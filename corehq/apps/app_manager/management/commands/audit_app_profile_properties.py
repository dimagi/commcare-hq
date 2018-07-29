from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.commcare_settings import get_custom_commcare_settings
import six

logger = logging.getLogger('audit_app_profile_properties')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Determine how many apps have changed their profile properties from the default values.
    '''

    def handle(self, **options):
        domains = [row['key'] for row in Domain.get_all(include_docs=False)]
        settings = {s['id']: s['default'] for s in get_custom_commcare_settings() if 'default' in s}
        deviant_counts = {id: 0 for id in settings.keys()}
        app_count = 0
        for domain in domains:
            for app in get_apps_in_domain(domain, include_remote=False):
                #logger.info("looking at app {}".format(app.id))
                if ('properties' in app.profile):
                    app_count = app_count + 1
                    for id, default in six.iteritems(settings):
                        if (id not in app.profile['properties']):
                            #logger.info("{}: not found".format(id))
                            pass
                        elif (app.profile['properties'][id] != default):
                            #logger.info("{}: {} != {}".format(id, app.profile['properties'][id], default))
                            deviant_counts[id] = deviant_counts[id] + 1
                        else:
                            #logger.info("{}: {} == {}".format(id, app.profile['properties'][id], default))
                            pass
        for id, count in six.iteritems(deviant_counts):
            logger.info("{}\t{}".format(count, id))
        logger.info('done with audit_app_profile_properties, examined {} apps in {} domains'.format(app_count, len(domains)))
