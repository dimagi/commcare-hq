from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0003_remove_null_True'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='locationtype',
            unique_together=set([('domain', 'name'), ('domain', 'code')]),
        ),
    ]
