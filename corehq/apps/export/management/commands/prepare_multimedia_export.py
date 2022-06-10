from django.core.management.base import BaseCommand
from corehq.apps.export.const import MAX_MULTIMEDIA_EXPORT_SIZE

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import get_export_query
from corehq.apps.reports.analytics.esaccessors import media_export_is_too_big


def _forms_with_attachments(es_query):
    query = es_query.source(['_id', 'external_blobs'])

    for form in query.scroll():
        try:
            for attachment in form.get('external_blobs', {}).values():
                if attachment['content_type'] != "text/xml":
                    yield form
                    continue
        except AttributeError:
            pass


def convert_bytes(size):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0

    return size


class Command(BaseCommand):
    help = "Gets multimedia files linked to export instance id"

    def add_arguments(self, parser):
        parser.add_argument(
            'export_id',
            help="The id of the export which files are wanted"
        )

    def handle(self, **options):
        try:
            export_id = options.pop('export_id')
            export = get_properly_wrapped_export_instance(export_id)
            filters = export.get_filters()
            query = get_export_query(export, filters)

            size = 0
            file_count = 0
            for form in _forms_with_attachments(query):
                for attachment in form.get('external_blobs', {}).values():
                    attachment_size = attachment.get('content_length', 0)
                    size += attachment_size
                    file_count = file_count + 1
                    print("file number : {}".format(file_count))
                    print("attachment size: {}".format(convert_bytes(attachment_size)))
                    print("current multimedia size: {}".format(convert_bytes(size)))
                    if size > MAX_MULTIMEDIA_EXPORT_SIZE:
                        print(
                            "multimedia export size {} is larger than the limit of {}".format(
                                convert_bytes(size),
                                convert_bytes(MAX_MULTIMEDIA_EXPORT_SIZE)
                            )
                        )
                        return
            print("success!")
            return
        except Exception as e:
            print(e)
