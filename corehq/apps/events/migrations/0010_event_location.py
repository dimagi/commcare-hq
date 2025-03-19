from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0020_delete_locationrelation'),
        ('events', '0009_attendeemodel'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='location',
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='locations.sqllocation',
                to_field='location_id',
            ),
        ),
    ]
