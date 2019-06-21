from __future__ import absolute_import
from __future__ import unicode_literals
import mock
import postgres_copy
import six
import sqlalchemy
import os

from django.test.utils import override_settings
from mock.mock import Mock

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import connection_manager, UCR_ENGINE_ID
from io import open


def setUpModule():
    if isinstance(Domain.get_db(), Mock):
        # needed to skip setUp for javascript tests thread on Travis
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()

    domain = create_domain('champ-cameroon')

    try:
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
                postgres_copy.copy_from(
                    f, table, engine, format='csv' if six.PY3 else b'csv',
                    null='' if six.PY3 else b'', header=True
                )
    except Exception:
        tearDownModule()
        raise

    _call_center_domain_mock.stop()


def tearDownModule():
    if isinstance(Domain.get_db(), Mock):
        # needed to skip setUp for javascript tests thread on Travis
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()

    configs = StaticDataSourceConfiguration.by_domain('champ-cameroon')
    adapters = [get_indicator_adapter(config) for config in configs]

    for adapter in adapters:
        adapter.drop_table()

    Domain.get_by_name('champ-cameroon').delete()
    _call_center_domain_mock.stop()
