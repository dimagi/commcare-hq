
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0002_auto_20160505_2058'),
    ]

    operations = [
        migrations.CreateModel(
            name='LastSeenNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('last_seen_date', models.DateTimeField()),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, unique=True, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
