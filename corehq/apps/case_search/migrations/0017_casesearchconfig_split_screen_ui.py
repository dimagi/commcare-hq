from django.db import migrations, models
from corehq.toggles import StaticToggle
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def populate_split_screen_ui(apps, schema_editor):
    CaseSearchConfig = apps.get_model('case_search', 'CaseSearchConfig')

    for domain in get_enabled_domains('split_screen_case_search'):
        CaseSearchConfig.objects.update_or_create(
            pk=domain,
            defaults={'split_screen_ui': True},
        )


def get_enabled_domains(toggle_slug):
    toggle = StaticToggle(toggle_slug, '', '')
    return toggle.get_enabled_domains()


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0016_csqlfixtureexpression_user_data_criteria'),
    ]

    operations = [
        migrations.AddField(
            model_name='casesearchconfig',
            name='split_screen_ui',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            populate_split_screen_ui,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
