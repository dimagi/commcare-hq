from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0007_remove_pillowerror_queued'),
    ]

    operations = [
        # doc_id index already covered by unique(doc_id, pillow)
        migrations.AlterField(
            model_name='pillowerror',
            name='doc_id',
            field=models.CharField(max_length=255),
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS pillow_retry_pillowerror_doc_id_480cab757780131d_like",
            migrations.RunSQL.noop
        )
    ]
