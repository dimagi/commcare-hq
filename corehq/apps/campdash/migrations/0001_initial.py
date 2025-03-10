from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignDashboard',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.CharField(max_length=255)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'app_label': 'campdash',
            },
        ),
        migrations.CreateModel(
            name='DashboardGauge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('gauge_type', models.CharField(choices=[('progress', 'Progress'), ('percentage', 'Percentage'), ('count', 'Count')], default='progress', max_length=20)),
                ('data_source', models.CharField(blank=True, max_length=255, null=True)),
                ('min_value', models.IntegerField(default=0)),
                ('max_value', models.IntegerField(default=100)),
                ('current_value', models.IntegerField(default=0)),
                ('display_order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('dashboard', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='gauges', to='campdash.campaigndashboard')),
            ],
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
            },
        ),
        migrations.CreateModel(
            name='DashboardReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('report_type', models.CharField(choices=[('table', 'Table'), ('chart', 'Chart'), ('list', 'List')], default='table', max_length=20)),
                ('data_source', models.CharField(blank=True, max_length=255, null=True)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('display_order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('dashboard', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='reports', to='campdash.campaigndashboard')),
            ],
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
            },
        ),
        migrations.CreateModel(
            name='DashboardMap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('map_type', models.CharField(choices=[('markers', 'Markers'), ('heatmap', 'Heat Map'), ('choropleth', 'Choropleth')], default='markers', max_length=20)),
                ('data_source', models.CharField(blank=True, max_length=255, null=True)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('display_order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('dashboard', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='maps', to='campdash.campaigndashboard')),
            ],
            options={
                'app_label': 'campdash',
                'ordering': ['display_order'],
            },
        ),
    ] 