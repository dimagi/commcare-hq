from django.db import migrations

from corehq.util.django_migrations import block_upgrade_for_removed_migration


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0018_auto_20200619_1626'),
    ]

    operations = [
        block_upgrade_for_removed_migration('4c7d3a96e061680bc87567d5916ae1e90dd60858')
    ]
