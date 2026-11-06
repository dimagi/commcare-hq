from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document_templates', '0002_template_deleted'),
    ]

    operations = [
        migrations.RenameField(
            model_name='template',
            old_name='variables',
            new_name='areas',
        ),
    ]
