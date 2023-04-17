from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_alter_event__case_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendeeModel',
            fields=[
                ('case_id', models.UUIDField(primary_key=True, serialize=False)),
                ('domain', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('locations', models.TextField(blank=True, default='')),
                ('primary_location', models.TextField(blank=True, default=None, null=True)),
                ('user_id', models.TextField(blank=True, max_length=36, null=True)),
            ],
            options={
                'managed': False,  # Does not create a DB table
            },
        ),
    ]
