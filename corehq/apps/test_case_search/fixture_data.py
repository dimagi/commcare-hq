from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from .const import TEST_DOMAIN_NAME


@dataclass(frozen=True)
class Patient:
    name: str
    address: str

    def to_json(self):
        # This mimics the return value of CommCareCaseSQL.to_json()
        case_id = str(uuid4())
        user_id = str(uuid4())
        xform_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        properties = {
            'address': self.address,
        }

        return {**properties, **{
            '_id': case_id,
            'doc_type': 'CommCareCase',
            'user_id': user_id,
            'case_json': properties,
            'case_id': case_id,
            'domain': TEST_DOMAIN_NAME,
            'type': 'patient',
            'name': self.name,
            'owner_id': user_id,
            'opened_on': now,
            'opened_by': user_id,
            'modified_on': now,
            'server_modified_on': now,
            'modified_by': user_id,
            'closed': False,
            'closed_on': None,
            'closed_by': None,
            'deleted': False,
            'external_id': None,
            'location_id': None,
            'indices': [],
            'actions': [OrderedDict([('xform_id', xform_id),
                                    ('server_date', now),
                                    ('date', now),
                                    ('sync_log_id', None)])],
            'xform_ids': [xform_id],
            'case_attachments': {},
            'backend_id': 'sql'
        }}


CASES_FIXTURE = [
    Patient("P. Sherman", "42 Wallaby Way"),
    Patient("Peter Sherman", "42 Wallaby Way, Sydney AU"),
    Patient("Paul Sherman", "#42 Wallaby Way, Sydney AU"),
]
