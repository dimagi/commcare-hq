from django.db import migrations, models
from django.db.models.functions import Lower

from corehq.apps.app_manager.const import get_template_app_plan_choices


def delete_legacy_exchange_applications(apps, schema_editor):
    apps.get_model('app_manager', 'ExchangeApplication').objects.using(
        schema_editor.connection.alias
    ).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0033_delete_publicformsession_delete_publicwebform'),
    ]

    operations = [
        # Existing records lack the required catalog metadata. Intentionally irreversible.
        migrations.RunPython(delete_legacy_exchange_applications),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(model_name='exchangeapplication', name='changelog_link'),
                migrations.RemoveField(model_name='exchangeapplication', name='required_privileges'),
            ],
        ),
        migrations.CreateModel(
            name='TemplateAppSector',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64)),
            ],
            options={
                'constraints': [models.UniqueConstraint(
                    Lower('name'), name='unique_template_app_sector_name_ci',
                )],
            },
        ),
        migrations.AddField(
            model_name='exchangeapplication', name='category',
            field=models.CharField(max_length=32, choices=[
                ('starter_app', 'Starter App'), ('feature_template', 'Feature Template'),
            ]),
        ),
        migrations.AddField(
            model_name='exchangeapplication', name='description',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='exchangeapplication', name='minimum_plan_edition',
            field=models.CharField(max_length=25, choices=get_template_app_plan_choices),
        ),
        migrations.AddField(
            model_name='exchangeapplication', name='sectors',
            field=models.ManyToManyField(
                to='app_manager.templateappsector', related_name='exchange_applications', blank=True,
            ),
        ),
    ]
