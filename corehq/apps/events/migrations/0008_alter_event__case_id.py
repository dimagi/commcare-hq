from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0007_alter_event_attendee_list_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='_case_id',
            field=models.UUIDField(default=None, null=True),
        ),
    ]
