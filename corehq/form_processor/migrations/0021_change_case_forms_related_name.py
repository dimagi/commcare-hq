from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0020_rename_index_relationship'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseforms',
            name='case',
            field=models.ForeignKey(related_query_name='xform', related_name='xform_set', db_column='case_uuid', to_field='case_uuid', to='form_processor.CommCareCaseSQL', db_index=False, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
