from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='requestlog',
            name='payload_id',
            field=models.CharField(blank=True, max_length=126, null=True),
        ),
    ]
