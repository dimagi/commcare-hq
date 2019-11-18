from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0010_add_auth_and_openrosa_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='xforminstancesql',
            name='deprecated_form_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='edited_on',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='orig_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', db_column='case_uuid', to_field='case_uuid', to='form_processor.CommCareCaseSQL', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='xform',
            field=models.ForeignKey(to='form_processor.XFormInstanceSQL', db_column='form_uuid', to_field='form_uuid', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
