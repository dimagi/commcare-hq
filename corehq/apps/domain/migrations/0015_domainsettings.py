from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0014_appreleasemodesetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='DomainSettings',
            fields=[
                ('domain', models.CharField(
                    max_length=255,
                    primary_key=True,
                    serialize=False,
                )),
                ('redirect_base_url', models.CharField(
                    blank=True,
                    default='',
                    max_length=255,
                )),
            ],
        ),
    ]
