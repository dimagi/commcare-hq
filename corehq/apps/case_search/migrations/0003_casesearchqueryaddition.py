from django.db import migrations, models

import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0002_auto_20161114_1901'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseSearchQueryAddition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=256, db_index=True)),
                ('name', models.CharField(max_length=256)),
                ('query_addition', jsonfield.fields.JSONField(default=dict)),
            ],
        ),
    ]
