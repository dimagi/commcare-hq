from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        migrations.AddField(
            model_name='requestlog',
            name='response_headers',
            field=jsonfield.fields.JSONField(blank=True, null=True),
        ),
    ]
