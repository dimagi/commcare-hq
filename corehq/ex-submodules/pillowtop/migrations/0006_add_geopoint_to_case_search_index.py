from django.db import migrations


class Migration(migrations.Migration):
    """This migration no longer has any operations. In the past this migration
    updated the mapping on the Elasticsearch `case_search` index. That operation
    has been removed because it was merged further in the past than our
    downstream hosters support window, making it safe to skip from now on.
    """

    dependencies = [
        ('pillowtop', '0005_kafkacheckpoint_doc_modification_time'),
    ]

    operations = []
