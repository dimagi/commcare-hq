from django.db import migrations

from corehq.util.django_migrations import block_upgrade_for_removed_migration


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0020_user_staging_pk_to_bigint'),
    ]

    operations = [
        block_upgrade_for_removed_migration('a7c40ca6acf609b22b495ab986c11f3524b47ce7')
    ]
