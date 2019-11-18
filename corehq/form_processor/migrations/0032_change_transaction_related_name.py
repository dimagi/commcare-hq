from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0031_add_details_field_to_case_transaction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', db_column='case_uuid', to_field='case_uuid', to='form_processor.CommCareCaseSQL', db_index=False, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
