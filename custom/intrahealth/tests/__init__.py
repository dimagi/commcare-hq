from __future__ import absolute_import
from __future__ import unicode_literals
import mock
import postgres_copy
import sqlalchemy
import os

from django.test.utils import override_settings
from mock.mock import Mock

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.locations.models import SQLLocation, LocationType
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

    domain = create_domain('test-pna')
    region_location_type = LocationType.objects.create(
        domain='test-pna',
        name='R\u00e9gion',
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='Region Test',
        location_id='8cde73411ddc4488a7f913c99499ead4',
        location_type=region_location_type
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='PASSY',
        location_id='1991b4dfe166335e342f28134b85fcac',
        location_type=region_location_type
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='r1',
        location_id='582c5d65a307baa7a38e7b5e651fd5fc',
        location_type=region_location_type
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='r2',
        location_id='942e078b8dfa9551a9ff799301b08642',
        location_type=region_location_type
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='r3',
        location_id='1991b4dfe166335e342f28134b85f516',
        location_type=region_location_type
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='r4',
        location_id='abb51a7f4ab64b70b899d86e54e62f51',
        location_type=region_location_type
    )

    district_location_type = LocationType.objects.create(
        domain='test-pna',
        name='District',
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='District Test',
        location_id='3db74fac2bad4e708e2b03800cc5ab73',
        location_type=district_location_type
    )

    pps_location_type = LocationType.objects.create(
        domain='test-pna',
        name='PPS',
    )

    SQLLocation.objects.create(
        domain='test-pna',
        name='P2',
        location_id='ccf4430f5c3f493797486d6ce1c39682',
        location_type=pps_location_type
    )

    SQLProduct.objects.create(
        domain='test-pna',
        name='Product 7',
        code='p7',
        product_id='p7'
    )

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
                postgres_copy.copy_from(f, table, engine, format=b'csv', null=b'', header=True)
    _call_center_domain_mock.stop()


def tearDownModule():
    if isinstance(Domain.get_db(), Mock):
        # needed to skip setUp for javascript tests thread on Travis
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    domain = Domain.get_by_name('test-pna')
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
