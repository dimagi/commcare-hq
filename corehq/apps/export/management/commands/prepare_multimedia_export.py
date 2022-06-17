from datetime import datetime
import traceback
from django.core.management.base import BaseCommand
from corehq.apps.export.const import MAX_MULTIMEDIA_EXPORT_SIZE

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import get_export_query
from corehq.apps.export.models.new import DatePeriod


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


def create_date_period(start_date, end_date):
    start_date = datetime.strptime(start_date, '%d-%m-%Y')
    end_date = datetime.strptime(end_date, '%d-%m-%Y')

    if end_date.day is start_date.day:
        days = 1
    else:
        days = end_date.day - start_date.day

    return DatePeriod(
        period_type="range",
        days=days,
        begin=start_date,
        end=end_date,
    )


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
        parser.add_argument(
            'user',
            help="The id of the user to filter by"
        )
        parser.add_argument(
            'start_date',
            help="The start date to filter by"
        )
        parser.add_argument(
            'end_date',
            help="The end date to filter by"
        )

    def handle(self, export_id, user, start_date, end_date, **options):
        try:
            date_period = create_date_period(start_date, end_date)

            export = get_properly_wrapped_export_instance(export_id)
            export.filters.date_period = date_period
            export.filters.users = [user]

            filters = export.get_filters()

            query = get_export_query(export, filters)

            size = 0
            file_count = 0
            unique_ids = []
            for form in _forms_with_attachments(query):
                for attachment in form.get('external_blobs', {}).values():
                    attachment_size = attachment.get('content_length', 0)
                    attachment_id = attachment.get('id', 0)

                    if attachment_id not in unique_ids:
                        unique_ids.append(attachment_id)

                    size += attachment_size
                    file_count = file_count + 1
                    print("file number : {}".format(file_count))
                    print("id : {}".format(attachment_id))
                    print("attachment size: {}".format(convert_bytes(attachment_size)))
                    print("current multimedia size: {}".format(convert_bytes(size)))
                    if size > MAX_MULTIMEDIA_EXPORT_SIZE:
                        print(
                            "multimedia export size {} is larger than the limit of {}".format(
                                convert_bytes(size),
                                convert_bytes(MAX_MULTIMEDIA_EXPORT_SIZE)
                            )
                        )
                        print("amount of unique files: {}".format(len(unique_ids)))
                        return
            print("success!")
            return
        except Exception as e:
            print(e)
            traceback.print_exc()
