from corehq.blobs import get_blob_db

BUCKET = 'case_importer/upload_files'


def write_case_import_file(f):
    db = get_blob_db()
    blob_info = db.put(f, bucket=BUCKET)
    return blob_info.identifier


def read_case_import_file(identifier):
    db = get_blob_db()
    return db.get(identifier, bucket=BUCKET)
