from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0008_add_index_for_caseforms_case_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='XFormOperationSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user', models.CharField(max_length=255, null=True)),
                ('operation', models.CharField(max_length=255)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('xform', models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field='form_uuid', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, 'normal'), (1, 'archived'), (2, 'deprecated'), (3, 'duplicate'), (4, 'error'), (5, 'submission_error')]),
            preserve_default=True,
        ),
    ]
