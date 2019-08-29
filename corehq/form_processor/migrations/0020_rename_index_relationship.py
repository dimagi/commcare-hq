
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0019_allow_closed_by_null'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecaseindexsql',
            old_name='relationship',
            new_name='relationship_id',
        ),
    ]
