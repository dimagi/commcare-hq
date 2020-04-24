from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0041_noop_specify_table_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, 'form'), (1, 'rebuild_with_reason'), (2, 'user_requested_rebuild'), (4, 'user_archived_rebuild'), (8, 'form_archive_rebuild'), (16, 'form_edit_rebuild'), (32, 'ledger')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, 'normal'), (1, 'archived'), (2, 'deprecated'), (4, 'duplicate'), (8, 'error'), (16, 'submission_error')]),
            preserve_default=True,
        ),
    ]
