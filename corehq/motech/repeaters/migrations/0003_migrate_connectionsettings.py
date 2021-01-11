from django.db import migrations

from corehq.motech.repeaters.models import Repeater


def _migrate_to_connectionsettings(apps, schema_editor):
    for repeater in iter_repeaters():
        if not repeater.connection_settings_id:
            repeater.create_connection_settings()


def iter_repeaters():
    for result in Repeater.get_db().view('repeaters/repeaters',
                                         reduce=False,
                                         include_docs=True).all():
        yield Repeater.wrap(result['doc'])


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0002_sqlrepeatrecord'),
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        migrations.RunPython(_migrate_to_connectionsettings,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
