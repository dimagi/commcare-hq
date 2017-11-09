from __future__ import print_function
from __future__ import absolute_import

from django.core.management import BaseCommand

from corehq.apps.es import CaseSearchES
from corehq.apps.userreports.management.commands.async_rebuild_table import CASE_DOC_TYPE, FakeChange
from corehq.apps.userreports.models import get_datasource_config, AsyncIndicator


class Command(BaseCommand):

    def handle(self, *args, **options):
        domain = 'enikshay'
        case_type = 'episode'
        cases_to_rebuild = (CaseSearchES()
                            .domain(domain)
                            .case_property_filter('migration_type', 'pmdt_excel')
                            .case_type(case_type)
                            .get_ids())

        configs = []
        for data_source_id in ['static-enikshay-epsiode_2b_v3', 'static-enikshay-epsiode_drtb_v2']:
            config, _ = get_datasource_config(data_source_id, domain)
            assert config.asynchronous
            assert config.referenced_doc_type == CASE_DOC_TYPE
            configs.append(config)

        fake_change_doc = {'doc_type': CASE_DOC_TYPE, 'domain': domain}

        config_ids = [config._id for config in configs]
        for case_id in cases_to_rebuild:
            change = FakeChange(case_id, fake_change_doc)
            AsyncIndicator.update_indicators(change, config_ids)
