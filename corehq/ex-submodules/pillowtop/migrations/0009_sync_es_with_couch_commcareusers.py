from django.db import migrations
from django.core.management import call_command
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def sync_couch_commcareusers_with_es(*args, **kwargs):
    call_command('sync_es_users', doc_types='CommCareUser', progress_key='0009_commcareusers_migration')


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0008_sync_es_with_couch_webusers'),
    ]

    operations = [
        migrations.RunPython(sync_couch_commcareusers_with_es)
    ]
