from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0004_create_repeaterstubs'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='repeaterstub',
            constraint=models.UniqueConstraint(fields=('repeater_id',),
                                               name='one_to_one_repeater'),
        ),
    ]
