from django.db import migrations, models

from corehq.util.django_migrations import run_management_command


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0023_add_remaining_content_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='ivrsurveycontent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        migrations.AddField(
            model_name='smssurveycontent',
            name='app_id',
            field=models.CharField(max_length=126, null=True),
        ),
        run_management_command(
            'populate_app_id_for_scheduling', required_commit='8e8243bc80964e6981fcb89a712776e9faf97397'
        )
    ]
