from corehq.apps.cleanup.management.commands.couch_migrate import Command as MigrateCommand
from corehq.apps.cleanup.pillows import DevicelogMigrationPillow


class Command(MigrateCommand):
    pillow_class = DevicelogMigrationPillow
