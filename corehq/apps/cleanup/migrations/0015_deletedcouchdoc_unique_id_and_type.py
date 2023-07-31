from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0014_deletedcouchdoc'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='deletedcouchdoc',
            constraint=models.UniqueConstraint(fields=('doc_id', 'doc_type'), name='deletedcouchdoc_unique_id_and_type'),
        ),
    ]
