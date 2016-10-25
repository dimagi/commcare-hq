import logging
from datetime import datetime
from django.core.management import BaseCommand
from django.http import Http404

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.es.domains import DomainES
from corehq.apps.es.apps import AppES


logger = logging.getLogger('app_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    help = '''
        Identify forms that were migrated because they had preload values,
        even though they did not require a case, which breaks the form.
    '''

    def handle(self, *args, **options):
        # Find all apps using vellum case management
        app_query = AppES().is_build(False).term('vellum_case_management', True).source(['domain', '_id'])

        # Find all domains created after vellum case management was released,
        # since their apps were never in the old world and therefore never migrated
        epoch = datetime(year=2016, month=7, day=15)
        domain_query = DomainES().date_range('date_created', gt=epoch).source('name')
        new_domains = {d['name']: 1 for d in domain_query.run().hits}

        hits = app_query.run().hits
        for hit in hits:
            if hit['domain'] not in new_domains:
                try:
                    app = get_app(hit['domain'], hit['_id'])
                    modules = [m for m in app.modules if m.module_type == 'basic']
                    for module in modules:
                        forms = [f for f in module.forms if f.doc_type == 'Form']
                        for form in forms:
                            if form.requires != 'case' and 'load' in form.case_references:
                                if form.case_references['load']:
                                    logger.info(
                                        '{} is suspicious: /a/{}/apps/view/{}/modules-{}/forms-{}'.format(
                                            form.unique_id, app.domain, app.id, module.id, form.id))
                except Http404:
                    pass
        logger.info('done with cmitfb_identify_broken_forms')
