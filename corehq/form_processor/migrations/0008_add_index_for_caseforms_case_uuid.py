from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0007_index_case_uuid_on_commcarecaseindex'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseForms',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_uuid', models.CharField(max_length=255)),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=False, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='caseforms',
            unique_together=set([('case', 'form_uuid')]),
        ),
    ]
