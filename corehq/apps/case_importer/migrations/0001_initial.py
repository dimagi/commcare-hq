from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CaseUploadRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=256)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('upload_id', models.UUIDField()),
                ('task_id', models.UUIDField()),
            ],
        ),
    ]
