import os
from contextlib import ExitStack, contextmanager
from unittest import mock

from django.test.utils import override_settings

import postgres_copy
import sqlalchemy
from unmagic import fixture

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID, connection_manager
from custom.up_nrhm.sql_data import DOMAIN


@fixture(scope="package", autouse=__file__)
def up_nrhm_context():
    def with_db(func):
        with db_blocker.unblock():
            func()

    @contextmanager
    def up_nrhm_domain():
        domain = create_domain(DOMAIN)
        yield domain
        with call_center_domain_mock, db_blocker.unblock():
            domain.delete()

    call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider')
    db_blocker = fixture("django_db_blocker")()
    with ExitStack() as on_exit:
        with (
            call_center_domain_mock,
            override_settings(SERVER_ENVIRONMENT='production'),
            db_blocker.unblock(),
        ):
            domain = on_exit.enter_context(up_nrhm_domain())

            configs = StaticDataSourceConfiguration.by_domain(domain.name)
            adapters = [get_indicator_adapter(config) for config in configs]
            for adapter in adapters:
                adapter.build_table()
                on_exit.callback(with_db, adapter.drop_table)

            engine = connection_manager.get_engine(UCR_ENGINE_ID)
            metadata = sqlalchemy.MetaData(bind=engine)
            metadata.reflect(bind=engine, extend_existing=True)
            path = os.path.join(os.path.dirname(__file__), 'fixtures')
            for file_name in os.listdir(path):
                with open(os.path.join(path, file_name), encoding='utf-8') as f:
                    table_name = get_table_name(domain.name, file_name[:-4])
                    table = metadata.tables[table_name]
                    postgres_copy.copy_from(f, table, engine, format='csv', null='', header=True)
                    on_exit.callback(with_db, table.drop)

        yield  # NOTE outside call_center_domain_mock / override_settings / db-unblock context
