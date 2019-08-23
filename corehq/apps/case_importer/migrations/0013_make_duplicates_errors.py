from __future__ import absolute_import, unicode_literals

from django.db import migrations

import six
from six.moves import range

from corehq.apps.case_importer.exceptions import TooManyMatches
from corehq.apps.case_importer.tracking.task_status import (
    TaskStatusResultError,
)
from corehq.util.django_migrations import skip_on_fresh_install


def iterator(queryset):
    chunk_size = 1000
    total = queryset.count()
    for start in range(0, total, chunk_size):
        end = start + chunk_size
        for record in queryset[start:end]:
            yield record


@skip_on_fresh_install
def migrate_record_duplicates(apps, schema_editor):
    CaseUploadRecord = apps.get_model('case_importer', 'CaseUploadRecord')
    for record in iterator(CaseUploadRecord.objects.all()):
        if record.task_status_json:
            result = record.task_status_json.get('result')
            if result and 'too_many_matches' in result:
                if result.pop('too_many_matches', 0):
                    result['errors'].append(
                        TaskStatusResultError(
                            title=TooManyMatches.title,
                            description=six.text_type(TooManyMatches.message),
                            rows=[],
                        ).to_json()
                    )
                record.save()


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0012_auto_20190405_1747'),
    ]

    operations = [
        migrations.RunPython(migrate_record_duplicates),
    ]
