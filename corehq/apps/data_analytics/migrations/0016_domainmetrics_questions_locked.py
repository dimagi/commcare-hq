from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0015_domainmetrics_public_webform_submissions_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainmetrics',
            name='questions_locked',
            field=models.IntegerField(null=True),
        ),
    ]
