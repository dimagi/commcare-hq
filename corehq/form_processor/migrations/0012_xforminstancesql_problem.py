from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0011_add_fields_for_deprecation'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='problem',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
