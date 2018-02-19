from __future__ import absolute_import
import mock
import postgres_copy
import sqlalchemy
import os

from django.test.testcases import TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import WebUser
from corehq.sql_db.connections import connection_manager, UCR_ENGINE_ID

TABLE_MAPPING = {
    'champ_client_forms': 'config_report_champ-cameroon_champ_client_forms_2a4922c5',
    'enhanced_peer_mobilization': 'config_report_champ-cameroon_enhanced_peer_mobilizatio_ce183c3b'
}


def setUpModule():
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()

    domain = create_domain('champ-cameroon')

    configs = StaticDataSourceConfiguration.by_domain(domain.name)
    adapters = [get_indicator_adapter(config) for config in configs]

    for adapter in adapters:
        adapter.build_table()

    engine = connection_manager.get_engine(UCR_ENGINE_ID)
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine, extend_existing=True)
    path = os.path.join(os.path.dirname(__file__), 'fixtures')
    for file_name in os.listdir(path):
        with open(os.path.join(path, file_name)) as f:
            table_name = TABLE_MAPPING[file_name[:-4]]
            table = metadata.tables[table_name]
            postgres_copy.copy_from(f, table, engine, format='csv', null='', header=True)

    _call_center_domain_mock.stop()


class ChampTestCase(TestCase):

    def setUp(self):
        self.run_july_third_test = True
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('champ-cameroon')
        domain.is_active = True
        domain.save()
        self.domain = domain
        user = WebUser.all().first()
        if not user:
            user = WebUser.create(domain.name, 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user
