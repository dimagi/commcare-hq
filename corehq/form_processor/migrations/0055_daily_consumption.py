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
            field=models.PositiveSmallIntegerField(choices=[(1, b'form'), (2, b'rebuild_with_reason'), (4, b'user_requested_rebuild'), (8, b'user_archived_rebuild'), (16, b'form_archive_rebuild'), (32, b'form_edit_rebuild'), (64, b'ledger'), (128, b'case_create'), (256, b'case_close'), (1024, b'case_attachment'), (512, b'case_index')]),
            preserve_default=True,
        ),
    ]
