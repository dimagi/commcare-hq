from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ivr', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
    ]
