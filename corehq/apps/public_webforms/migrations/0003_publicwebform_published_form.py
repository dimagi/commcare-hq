from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('public_webforms', '0002_publicformsession_contact_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicwebform',
            name='xmlns',
            field=models.CharField(default=''),
            preserve_default=False,
        ),
    ]
