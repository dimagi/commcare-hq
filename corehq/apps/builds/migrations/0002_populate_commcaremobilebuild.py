from django.db import migrations


class Migration(migrations.Migration):
    # This was a couch-to-sql data population migration. The couch model and
    # its populate command have since been removed, so the operation is now a
    # no-op retained to preserve the migration history.

    dependencies = [
        ('builds', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
