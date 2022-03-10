import os

from django.test.utils import override_settings

from unittest import mock
import postgres_copy
import sqlalchemy

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID, connection_manager
from corehq.util.test_utils import require_db_context
from custom.up_nrhm.sql_data import DOMAIN


@require_db_context
def setUpModule():
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()

    domain = create_domain(DOMAIN)

    with override_settings(SERVER_ENVIRONMENT='production'):

        configs = StaticDataSourceConfiguration.by_domain(domain.name)
        adapters = [get_indicator_adapter(config) for config in configs]

        for adapter in adapters:
            adapter.build_table()

        engine = connection_manager.get_engine(UCR_ENGINE_ID)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect(bind=engine, extend_existing=True)
        path = os.path.join(os.path.dirname(__file__), 'fixtures')
        for file_name in os.listdir(path):
            with open(os.path.join(path, file_name), encoding='utf-8') as f:
                table_name = get_table_name(domain.name, file_name[:-4])
                table = metadata.tables[table_name]
                postgres_copy.copy_from(f, table, engine, format='csv', null='', header=True)
    _call_center_domain_mock.stop()


@require_db_context
def tearDownModule():
    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    domain = Domain.get_by_name(DOMAIN)
    engine = connection_manager.get_engine(UCR_ENGINE_ID)
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine, extend_existing=True)
    path = os.path.join(os.path.dirname(__file__), 'fixtures')
    for file_name in os.listdir(path):
        table_name = get_table_name(domain.name, file_name[:-4])
        table = metadata.tables[table_name]
        table.drop()
    _call_center_domain_mock.start()
    domain.delete()
    _call_center_domain_mock.stop()
