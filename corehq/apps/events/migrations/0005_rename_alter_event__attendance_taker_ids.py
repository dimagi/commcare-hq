import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_event_id_case_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='event',
            old_name='attendance_taker_ids',
            new_name='_attendance_taker_ids',
        ),
        migrations.AlterField(
            model_name='event',
            name='_attendance_taker_ids',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.UUIDField(), blank=True, default=list,
                null=True, size=None),
        ),
    ]
