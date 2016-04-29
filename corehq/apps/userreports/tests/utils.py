from datetime import datetime
from decimal import Decimal
import json
import os
import uuid
from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import data_sources
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from dimagi.utils.parsing import json_format_datetime
from pillowtop.feed.interface import Change, ChangeMeta


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
    date_opened = datetime(2014, 6, 21)
    sample_doc = dict(
        _id=uuid.uuid4().hex,
        opened_on=json_format_datetime(date_opened),
        owner_id='some-user-id',
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


def doc_to_change(doc):
    return Change(
        id=doc['_id'],
        sequence_id='0',
        document=doc,
        metadata=ChangeMeta(
            document_id=doc['_id'],
            data_source_type=data_sources.COUCH,
            data_source_name=CommCareCase.get_db().dbname,
            document_type=doc['doc_type'],
            document_subtype=doc['type'],
            domain=doc['domain'],
            is_deletion=False,
        )
    )


def domain_lite(name):
    from corehq.apps.callcenter.utils import DomainLite
    return DomainLite(name, None, None, True)
