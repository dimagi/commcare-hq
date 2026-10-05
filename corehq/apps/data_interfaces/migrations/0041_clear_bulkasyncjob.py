from django.db import migrations


def _delete_all_jobs(apps, schema_editor):
    from corehq.blobs import CODES, get_blob_db
    from corehq.blobs.models import BlobMeta

    BulkAsyncJob = apps.get_model('data_interfaces', 'BulkAsyncJob')
    blob_db = get_blob_db()

    for job_id in BulkAsyncJob.objects.values_list('id', flat=True):
        parent_id = job_id.hex
        success = blob_db.bulk_delete(metas=list(
            BlobMeta.objects.partitioned_query(parent_id).filter(
                parent_id=parent_id,
                type_code=CODES.bulk_async_job,
            )
        ))
        if not success:
            # Stop rather than delete the job row. Re-running is safe
            raise RuntimeError(f'bulk async job {parent_id}: blobs not deleted')

    BulkAsyncJob.objects.all().delete()


class Migration(migrations.Migration):

    # if we hit an error while deleting blobs, it is better to not rollback
    # blobmetas (only relevant on non-sharded environments). This makes the
    # migration resumable.
    atomic = False

    dependencies = [
        ('data_interfaces', '0040_bulkasyncjob'),
    ]

    operations = [
        migrations.RunPython(_delete_all_jobs, migrations.RunPython.noop),
    ]
