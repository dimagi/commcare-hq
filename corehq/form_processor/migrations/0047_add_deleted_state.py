from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0046_add_not_null_constraint_to_owner_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, 'normal'), (1, 'archived'), (2, 'deprecated'), (4, 'duplicate'), (8, 'error'), (16, 'submission_error'), (32, 'deleted')]),
            preserve_default=True,
        ),
    ]
