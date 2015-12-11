from collections import namedtuple
import os
import shutil
import tempfile
import uuid
import re
from casexml.apps.phone.exceptions import SyncLogCachingError
from casexml.apps.phone.models import get_properly_wrapped_sync_log


FileReference = namedtuple('FileReference', ['file', 'path'])


def copy_payload_and_synclog_and_get_new_file(filelike_payload):
    """
    Given a restore payload, extracts the sync log id and sync log from the payload,
    makes a copy of the sync log, and then returns a new FileReference with the same contents
    except using the new sync log ID.
    """
    synclog_id, end_position = extract_synclog_id_from_filelike_payload(filelike_payload)
    old_sync_log = get_properly_wrapped_sync_log(synclog_id)
    new_sync_log_doc = old_sync_log.to_json()
    new_sync_log_id = uuid.uuid4().hex
    new_sync_log_doc['_id'] = new_sync_log_id
    del new_sync_log_doc['_rev']
    old_sync_log.get_db().save_doc(new_sync_log_doc)
    return replace_sync_log_id_in_filelike_payload(
        filelike_payload, old_sync_log._id, new_sync_log_id, end_position
    )


def extract_synclog_id_from_filelike_payload(filelike_payload):
    filelike_payload.seek(0)
    try:
        beginning_of_log = filelike_payload.read(500)
        # i know, regex parsing xml is bad. not sure what to do since this is arbitrarily truncated
        match = re.search('<restore_id>([\w_-]+)</restore_id>', beginning_of_log)
        if not match:
            raise SyncLogCachingError("Couldn't find synclog ID from beginning of restore!")
        groups = match.groups()
        if len(groups) != 1:
            raise SyncLogCachingError("Found more than one synclog ID from beginning of restore! {}".format(
                ', '.join(groups))
            )
        return groups[0], beginning_of_log.index(groups[0])
    finally:
        filelike_payload.seek(0)


def replace_sync_log_id_in_filelike_payload(filelike_payload, old_id, new_id, position):
    filelike_payload.seek(0)
    try:
        beginning = filelike_payload.read(position)
        extracted_id = filelike_payload.read(len(old_id))
        if extracted_id != old_id:
            raise SyncLogCachingError('Error putting sync log back together. Expected ID {} but was {}'.format(
                old_id, extracted_id,
            ))
        # write the result to a new file
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as outfile:
            outfile.write(beginning)
            outfile.write(new_id)
            shutil.copyfileobj(filelike_payload, outfile)
        return FileReference(open(path, 'r'), path)
    finally:
        filelike_payload.seek(0)
