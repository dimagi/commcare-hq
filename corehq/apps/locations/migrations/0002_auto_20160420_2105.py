from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationtype',
            name='_expand_from',
            field=models.ForeignKey(related_name='+', db_column='expand_from', to='locations.LocationType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='locationtype',
            name='_expand_from_root',
            field=models.BooleanField(default=False, db_column='expand_from_root'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='locationtype',
            name='expand_to',
            field=models.ForeignKey(related_name='+', to='locations.LocationType', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
