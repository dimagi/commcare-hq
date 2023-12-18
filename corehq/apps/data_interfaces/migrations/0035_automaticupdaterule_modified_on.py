from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0034_case_name_actions'),
    ]

    operations = [
        migrations.AddField(
            model_name='automaticupdaterule',
            name='modified_on',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
