import uuid
from datetime import datetime
from corehq.warehouse.models import (
    UserStagingTable,
)


def create_user_staging_record(domain, user_id=None, username=None, doc_type=None, base_doc=None):
    record = UserStagingTable(
        user_id=user_id or uuid.uuid().hex,
        username=username or 'user-staging',
        doc_type=doc_type or 'CommCareUser',
        base_doc=base_doc or 'CouchUser',
        domain=domain,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        date_joined=datetime.utcnow(),
    )
    record.save()
    return record
