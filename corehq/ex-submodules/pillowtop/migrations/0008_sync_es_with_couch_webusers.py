from django.db import migrations
from django.core.management import call_command


def sync_couch_webusers_with_es(*args, **kwargs):
    call_command('sync_es_webusers')


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0007_copy_xforms_checkpoint'),
    ]

    operations = [
        migrations.RunPython(sync_couch_webusers_with_es)
    ]
