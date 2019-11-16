from django.db import transaction

from corehq.apps.hqmedia.models import ApplicationMediaMapping


def migrate_multimedia_map(doc):
    with transaction.atomic():
        for path, item in doc['multimedia_map'].items():
            sql_item = ApplicationMediaMapping.objects.create(
                domain=doc['domain'],
                app_id=doc['_id'],
                path=path,
                multimedia_id=item['multimedia_id'],
                media_type=item['media_type'],
                version=item['version'],
                unique_id=item['unique_id'] or ApplicationMediaMapping.gen_unique_id(item['multimedia_id'], path),
            )
            sql_item.save()
