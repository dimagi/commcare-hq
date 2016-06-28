import urllib
from celery.task import task

from corehq.apps.export.export import get_export_file, rebuild_export
from couchexport.models import Format
from couchexport.tasks import escape_quotes
from soil.util import expose_cached_download


@task
def populate_export_download_task(export_instances, filters, download_id, filename=None, expiry=10 * 60 * 60):
    export_file = get_export_file(
        export_instances,
        filters,
        # We don't have a great way to calculate progress if it's a bulk download,
        # so only track the progress for single instance exports.
        progress_tracker=populate_export_download_task if len(export_instances) == 1 else None
    )

    file_format = Format.from_format(export_file.format)
    filename = filename or export_instances[0].name
    escaped_filename = escape_quotes('%s.%s' % (filename, file_format.extension))
    escaped_filename = urllib.quote(escaped_filename.encode('utf8'))

    payload = export_file.file.payload
    expose_cached_download(
        payload,
        expiry,
        ".{}".format(file_format.extension),
        mimetype=file_format.mimetype,
        content_disposition='attachment; filename="%s"' % escaped_filename,
        download_id=download_id,
    )
    export_file.file.delete()


@task(queue='background_queue', ignore_result=True)
def rebuild_export_task(export_instance, last_access_cutoff=None, filter=None):
    rebuild_export(export_instance, last_access_cutoff, filter)
