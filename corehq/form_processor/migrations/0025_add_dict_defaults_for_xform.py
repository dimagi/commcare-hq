
from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0024_rename_case_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='auth_context',
            field=jsonfield.fields.JSONField(default=dict),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=jsonfield.fields.JSONField(default=dict),
            preserve_default=True,
        ),
    ]
