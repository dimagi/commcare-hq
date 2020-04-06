from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0012_xforminstancesql_problem'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_uuid', models.CharField(unique=False, max_length=255, db_index=False)),
                ('name', models.CharField(max_length=255, db_index=False)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('case', models.ForeignKey(related_query_name='attachment', related_name='attachments', db_column='case_uuid', to_field='case_uuid', to='form_processor.CommCareCaseSQL', db_index=False, on_delete=models.CASCADE)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='commcarecasesql',
            name='attachments_json',
        ),
    ]
