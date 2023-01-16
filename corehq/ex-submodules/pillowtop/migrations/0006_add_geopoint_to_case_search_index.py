from django.db import migrations

from corehq.util.django_migrations import (
    get_migration_name,
    prompt_for_historical_migration,
)


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0005_kafkacheckpoint_doc_modification_time'),
    ]

    operations = [
        prompt_for_historical_migration(
            'pillowtop', get_migration_name(__file__),
            # the commit (on 'master') that this branch is currently based on
            required_commit='08d594d1877cfe3ca20fcf8aa29155bce4ff26bf'
        )
    ]
