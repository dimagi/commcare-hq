from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('export', '0010_defaultexportsettings'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='incrementalexportcheckpoint',
            name='request_log',
        ),
    ]
