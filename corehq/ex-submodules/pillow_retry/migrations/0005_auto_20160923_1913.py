
from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0004_auto_drop_legacy_ucr_errors'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pillowerror',
            name='doc_date',
        ),
        migrations.RemoveField(
            model_name='pillowerror',
            name='doc_type',
        ),
        migrations.RemoveField(
            model_name='pillowerror',
            name='domains',
        ),
        migrations.AddField(
            model_name='pillowerror',
            name='change_metadata',
            field=jsonfield.fields.JSONField(null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pillowerror',
            name='change',
            field=jsonfield.fields.JSONField(null=True),
            preserve_default=True,
        ),
    ]
