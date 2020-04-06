from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0038_form_functions'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('entry_id', models.CharField(max_length=100, db_index=True)),
                ('section_id', models.CharField(max_length=100, db_index=True)),
                ('balance', models.IntegerField(default=0)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field='case_id', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, 'form'), (1, 'rebuild_with_reason'), (2, 'user_requested_rebuild'), (3, 'user_archived_rebuild'), (4, 'form_archive_rebuild'), (5, 'form_edit_rebuild'), (6, 'ledger')]),
            preserve_default=True,
        ),
    ]
