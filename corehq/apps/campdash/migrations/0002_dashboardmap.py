# Generated by Django 4.2.17 on 2025-03-07 11:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campdash', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_configuration', models.CharField(max_length=126)),
                ('display_order', models.IntegerField(default=1)),
                ('dashboard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_maps', to='campdash.campaigndashboard')),
            ],
            options={
                'ordering': ['display_order'],
                'indexes': [models.Index(fields=['display_order'], name='campdash_map_report_order_idx')],
            },
        ),
    ]
