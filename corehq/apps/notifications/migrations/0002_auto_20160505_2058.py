from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_squashed_0003_auto_20160504_2049'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='notification',
            options={'ordering': ['-activated']},
        ),
        migrations.AddField(
            model_name='notification',
            name='activated',
            field=models.DateTimeField(db_index=True, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(max_length=10, choices=[('info', 'Product Notification'), ('alert', 'Maintenance Notification')]),
            preserve_default=True,
        ),
    ]
