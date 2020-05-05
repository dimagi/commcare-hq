from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0054_ledgertransaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledgervalue',
            name='daily_consumption',
            field=models.DecimalField(null=True, max_digits=20, decimal_places=5),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'form'), (2, 'rebuild_with_reason'), (4, 'user_requested_rebuild'), (8, 'user_archived_rebuild'), (16, 'form_archive_rebuild'), (32, 'form_edit_rebuild'), (64, 'ledger'), (128, 'case_create'), (256, 'case_close'), (1024, 'case_attachment'), (512, 'case_index')]),
            preserve_default=True,
        ),
    ]
