from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0013_rename_sqlrepeaters_to_repeaters'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqlrepeatrecord',
            name='state',
            field=models.TextField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('SUCCESS', 'Succeeded'),
                    ('FAIL', 'Failed'),
                    ('CANCELLED', 'Cancelled'),
                    ('EMPTY', 'Empty'),
                ],
                default='PENDING',
            ),
        ),
        migrations.AlterField(
            model_name='sqlrepeatrecordattempt',
            name='state',
            field=models.TextField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('SUCCESS', 'Succeeded'),
                    ('FAIL', 'Failed'),
                    ('CANCELLED', 'Cancelled'),
                    ('EMPTY', 'Empty'),
                ],
            ),
        ),
    ]
