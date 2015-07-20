from datetime import datetime
from decimal import Decimal
import json
import os
from corehq import ReportConfiguration
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.util.dates import iso_string_to_date


def get_sample_report_config():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_report_config.json')
    with open(sample_file) as f:
        structure = json.loads(f.read())
        return ReportConfiguration.wrap(structure)


def get_sample_data_source():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_data_source.json')
    with open(sample_file) as f:
        structure = json.loads(f.read())
        return DataSourceConfiguration.wrap(structure)


def get_sample_doc_and_indicators(fake_time_now=None):
    if fake_time_now is None:
        fake_time_now = datetime.utcnow()
    date_opened = "2014-06-21"
    sample_doc = dict(
        _id='some-doc-id',
        opened_on=date_opened,
        owner_id='some-user-id',
        doc_type="CommCareCase",
        domain='user-reports',
        type='ticket',
        category='bug',
        tags='easy-win public',
        is_starred='yes',
        estimate=2.3,
        priority=4,
    )
    expected_indicators = {
        'doc_id': 'some-doc-id',
        'repeat_iteration': 0,
        'date': iso_string_to_date(date_opened),
        'owner': 'some-user-id',
        'count': 1,
        'category_bug': 1, 'category_feature': 0, 'category_app': 0, 'category_schedule': 0,
        'tags_easy-win': 1, 'tags_potential-dupe': 0, 'tags_roadmap': 0, 'tags_public': 1,
        'is_starred': 1,
        'estimate': Decimal(2.3),
        'priority': 4,
        'inserted_at': fake_time_now,
    }
    return sample_doc, expected_indicators
