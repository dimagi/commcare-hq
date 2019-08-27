
from django.db import models, migrations
import jsonfield.fields
import corehq.form_processor.abstract_models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0003_auto_20151104_2226'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommCareCaseSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('case_uuid', models.CharField(max_length=255)),
                ('domain', models.CharField(max_length=255)),
                ('case_type', models.CharField(max_length=255)),
                ('owner_id', models.CharField(max_length=255)),
                ('opened_on', models.DateTimeField()),
                ('opened_by', models.CharField(max_length=255)),
                ('modified_on', models.DateTimeField()),
                ('server_modified_on', models.DateTimeField()),
                ('modified_by', models.CharField(max_length=255)),
                ('closed', models.BooleanField(default=False)),
                ('closed_on', models.DateTimeField(null=True)),
                ('closed_by', models.CharField(max_length=255)),
                ('deleted', models.BooleanField(default=False)),
                ('external_id', models.CharField(max_length=255)),
                ('case_json', jsonfield.fields.JSONField(default='null')),
                ('attachments_json', jsonfield.fields.JSONField(default='null')),
            ],
            options={
            },
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractCommCareCase),
        ),
        migrations.AlterIndexTogether(
            name='commcarecasesql',
            index_together=set([('domain', 'owner_id'), ('domain', 'closed', 'server_modified_on')]),
        ),
    ]
