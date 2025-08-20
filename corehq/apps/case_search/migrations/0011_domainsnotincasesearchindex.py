from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0010_casesearchconfig_synchronous_web_apps'),
    ]

    operations = [
        migrations.CreateModel(
            name='DomainsNotInCaseSearchIndex',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=256)),
                ('estimated_size', models.IntegerField()),
            ],
        ),
    ]
