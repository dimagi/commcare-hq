
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0023_make_case_name_top_level'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_type',
            new_name='type',
        ),
    ]
