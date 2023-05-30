from django.db import migrations, models


def _set_status_under_review(apps, schema_editor):
    """
    If attendee_list_status is 'Not started' or 'In progress' then set
    it to 'Under review'.
    """
    Event = apps.get_model("events", "Event")
    db_alias = schema_editor.connection.alias
    Event.objects.using(db_alias).filter(
        attendee_list_status__in=('Not started', 'In progress')
    ).update(attendee_list_status='Under review')


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_remove_end_date_constraint'),
    ]

    operations = [
        migrations.RunPython(
            _set_status_under_review,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='event',
            name='attendee_list_status',
            field=models.CharField(choices=[
                ('Under review', 'Attendee list under review'),
                ('Rejected', 'Attendee list rejected'),
                ('Accepted', 'Attendee list accepted')
            ], default='Under review', max_length=255),
        ),
    ]
