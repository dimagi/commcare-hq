from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, date, time
from decimal import Decimal
import json
import os
import uuid
import re
import six
import sqlalchemy


from mock import patch
from six.moves import zip

from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.change_feed import data_sources
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.sql_db.connections import connection_manager
from dimagi.utils.parsing import json_format_datetime
from pillowtop.feed.interface import Change, ChangeMeta

from io import open


def get_sample_report_config():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_report_config.json')
    with open(sample_file, encoding='utf-8') as f:
        structure = json.loads(f.read())
        return ReportConfiguration.wrap(structure)


def get_sample_data_source():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_data_source.json')
    with open(sample_file, encoding='utf-8') as f:
        structure = json.loads(f.read())
        return DataSourceConfiguration.wrap(structure)


def get_data_source_with_related_doc_type():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'parent_child_data_source.json')
    with open(sample_file, encoding='utf-8') as f:
        structure = json.loads(f.read())
        return DataSourceConfiguration.wrap(structure)


def get_sample_doc_and_indicators(fake_time_now=None, owner_id='some-user-id'):
    if fake_time_now is None:
        fake_time_now = datetime.utcnow()
    date_opened = datetime(2014, 6, 21)
    sample_doc = dict(
        _id=uuid.uuid4().hex,
        opened_on=json_format_datetime(date_opened),
        owner_id=owner_id,
        doc_type="CommCareCase",
        domain='user-reports',
        name='sample name',
        type='ticket',
        category='bug',
        tags='easy-win public',
        is_starred='yes',
        estimate=2.3,
        priority=4,
    )
    expected_indicators = {
        'doc_id': sample_doc['_id'],
        'repeat_iteration': 0,
        'date': date_opened,
        'owner': owner_id,
        'count': 1,
        'category_bug': 1, 'category_feature': 0, 'category_app': 0, 'category_schedule': 0,
        'tags_easy-win': 1, 'tags_potential-dupe': 0, 'tags_roadmap': 0, 'tags_public': 1,
        'is_starred': 1,
        'estimate': Decimal(2.3),
        'priority': 4,
        'inserted_at': fake_time_now,
    }
    return sample_doc, expected_indicators


def doc_to_change(doc):
    return Change(
        id=doc['_id'],
        sequence_id='0',
        document=doc,
        metadata=ChangeMeta(
            document_id=doc['_id'],
            data_source_type=data_sources.SOURCE_COUCH,
            data_source_name=CommCareCase.get_db().dbname,
            document_type=doc['doc_type'],
            document_subtype=doc.get('type'),
            domain=doc['domain'],
            is_deletion=False,
        )
    )


def domain_lite(name):
    from corehq.apps.callcenter.utils import DomainLite
    return DomainLite(name, None, None, True)


def post_run_with_sql_backend(fn, *args, **kwargs):
    fn.doCleanups()
    fn.tearDown()


def pre_run_with_es_backend(fn, *args, **kwargs):
    fn.setUp()


def mock_datasource_config():
    return patch('corehq.apps.userreports.reports.data_source.get_datasource_config',
                 return_value=(get_sample_data_source(), None))


def get_simple_xform():
    xform = XFormBuilder()
    xform.new_question('first_name', 'First Name', data_type='string')
    xform.new_question('last_name', 'Last Name', data_type='string')
    xform.new_question('children', 'Children', data_type='int')
    xform.new_question('dob', 'Date of Birth', data_type='date')
    xform.new_question('state', 'State', data_type='select', choices={
        'MA': 'MA',
        'MN': 'MN',
        'VT': 'VT',
    })
    return xform.tostring().decode('utf-8')


def load_data_from_db(table_name):
    def _convert_decimal_to_string(value):
        value_str = str(value)
        p = re.compile('0E-(?P<zeros>[0-9]+)')
        match = p.match(value_str)
        if match:
            return '0.{}'.format(int(match.group('zeros')) * '0')
        else:
            return value_str

    engine = connection_manager.get_session_helper('default').engine
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine)
    table = metadata.tables[table_name]
    columns = [
        column.name
        for column in table.columns
    ]
    with engine.begin() as connection:
        for row in list(connection.execute(table.select())):
            row = list(row)
            for idx, value in enumerate(row):
                if isinstance(value, date):
                    row[idx] = value.strftime('%Y-%m-%d')
                elif isinstance(value, time):
                    row[idx] = value.strftime("%H:%M:%S.%f").rstrip('0').rstrip('.')
                elif isinstance(value, six.integer_types):
                    row[idx] = str(value)
                elif isinstance(value, (float, Decimal)):
                    row[idx] = _convert_decimal_to_string(row[idx])
                elif six.PY2 and isinstance(value, six.text_type):
                    row[idx] = value.encode('utf-8')
                elif value is None:
                    row[idx] = ''
            yield dict(zip(columns, row))


def mock_filter_missing_domains(configs):
    return configs


skip_domain_filter_patch = patch(
    'corehq.apps.userreports.pillow._filter_missing_domains', mock_filter_missing_domains
)
