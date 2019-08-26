from corehq.sql_db.operations import rename_table_indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0014_add_queuedsms'),
    ]

    operations = [
        rename_table_indexes('sms_phonenumber', 'sms_phoneblacklist'),
        migrations.RenameModel(
            old_name='PhoneNumber',
            new_name='PhoneBlacklist',
        ),
    ]
