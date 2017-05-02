from corehq.toggles import BLOBDB_RESTORE


def get_restore_response_class(domain):
    from casexml.apps.phone.restore import BlobRestoreResponse, FileRestoreResponse

    if BLOBDB_RESTORE.enabled(domain):
        return BlobRestoreResponse
    return FileRestoreResponse
