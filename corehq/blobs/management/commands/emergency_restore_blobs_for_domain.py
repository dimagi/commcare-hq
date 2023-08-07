# credit to Danny Roberts for the bulk of this code
from gzip import GzipFile
from io import BytesIO

from django.core.management import BaseCommand

from corehq.blobs import get_blob_db
from corehq.blobs.models import BlobMeta, DeletedBlobMeta
from corehq.form_processor.models.forms import XFormInstance


class Command(BaseCommand):
    """
    WARNING: intended to only be used in the rare circumstance blobs are unintentionally deleted from a domain
    If forms and cases have been hard deleted, you should restore the SQL form and case docs before running this
    Note you need the "s3:ListBucketVersions", "s3:GetObjectVersion" permissions added to the policy responsible
    for accessing S3 for this to work properly
    This command was only used to restore form xml and form attachments (BLOB_CODES 2 and 3). You may need to
    modify this to handle other types, specifically how the content is formatted in _get_stream_for_object_version
    """

    def handle(self, domain, **options):
        blob_metas = get_blob_metas_for_domain(domain)
        db = get_blob_db()
        restore_blobs(db, blob_metas)


def get_blob_metas_for_domain(domain):
    form_ids = XFormInstance.objects.get_form_ids_in_domain(domain)
    blob_metas = []
    for form_id in form_ids:
        blob_metas += _get_blob_metas(form_id)

    if not blob_metas:
        deleted_blobs = []
        for form_id in form_ids:
            deleted_blobs += _get_deleted_blob_metas(form_id)
        if deleted_blobs:
            print("You should restore the BlobMeta objects before attempting to restore actual blobs.")
            exit(1)

    return blob_metas


def restore_blobs(db, blob_metas):
    for meta in blob_metas:
        stream = _get_stream_of_latest_version_before_deletion_for_object(meta)
        db.put(stream, meta=meta)


def _get_blob_metas(parent_id):
    return BlobMeta.objects.partitioned_query(parent_id).filter(parent_id=parent_id)


def _get_deleted_blob_metas(parent_id):
    return DeletedBlobMeta.objects.partitioned_query(parent_id).filter(parent_id=parent_id)


def _get_stream_of_latest_version_before_deletion_for_object(meta):
    version_id = _get_latest_version_id_before_deletion_for_object(meta.key)
    return _get_stream_for_object_version(meta, version_id)


def _get_latest_version_id_before_deletion_for_object(key):
    versions_dict = _get_versions_dict_for_object(key)
    assert any(delete_marker['IsLatest'] for delete_marker in versions_dict['DeleteMarkers'])
    return sorted(
        versions_dict['Versions'], key=lambda version: version['LastModified'], reverse=True
    )[0]['VersionId']


def _get_stream_for_object_version(meta, version_id):
    object_dict = _get_object_dict_for_version(meta.key, version_id)
    if meta.is_compressed:
        return GzipFile(meta.key, mode='rb', fileobj=object_dict['Body'])
    else:
        return BytesIO(object_dict['Body'])


def _get_versions_dict_for_object(key):
    blob_db = get_blob_db()
    return blob_db.db.meta.client.list_object_versions(Bucket=blob_db.s3_bucket_name, Prefix=key)


def _get_object_dict_for_version(key, version_id):
    blob_db = get_blob_db()
    return blob_db.db.meta.client.get_object(Bucket=blob_db.s3_bucket_name, Key=key, VersionId=version_id)
