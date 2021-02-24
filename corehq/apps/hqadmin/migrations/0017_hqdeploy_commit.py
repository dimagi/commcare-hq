from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0016_hqdeploy_ordering'),
    ]

    operations = [
        migrations.AddField(
            model_name='hqdeploy',
            name='commit',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
