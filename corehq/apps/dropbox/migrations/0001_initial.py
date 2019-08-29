
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DropboxUploadHelper',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('dest', models.CharField(max_length=255)),
                ('src', models.CharField(max_length=255)),
                ('progress', models.DecimalField(default=0, max_digits=3, decimal_places=2)),
                ('download_id', models.CharField(max_length=255, db_index=True)),
                ('failure_reason', models.CharField(default=None, max_length=255, null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
