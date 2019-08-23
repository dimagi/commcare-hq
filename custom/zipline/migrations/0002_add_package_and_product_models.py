# -*- coding: utf-8 -*-

from django.db import models, migrations
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('zipline', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmergencyOrderPackage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('package_number', models.IntegerField()),
                ('products', jsonfield.fields.JSONField(default=dict)),
                ('status', models.CharField(default=b'dispatched', max_length=126)),
                ('cost', models.DecimalField(null=True, max_digits=12, decimal_places=3)),
                ('weight', models.DecimalField(null=True, max_digits=12, decimal_places=3)),
                ('cancelled_status', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True)),
                ('delivered_status', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True)),
                ('dispatched_status', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True)),
                ('order', models.ForeignKey(to='zipline.EmergencyOrder', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OrderableProduct',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126)),
                ('code', models.CharField(max_length=126)),
                ('name', models.CharField(max_length=126)),
                ('description', models.CharField(max_length=126)),
                ('cost', models.DecimalField(max_digits=12, decimal_places=3)),
                ('unit_description', models.CharField(max_length=126)),
                ('weight', models.DecimalField(max_digits=12, decimal_places=3)),
                ('max_units_allowed', models.IntegerField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OrderableProductHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126)),
                ('code', models.CharField(max_length=126)),
                ('name', models.CharField(max_length=126)),
                ('description', models.CharField(max_length=126)),
                ('cost', models.DecimalField(max_digits=12, decimal_places=3)),
                ('unit_description', models.CharField(max_length=126)),
                ('weight', models.DecimalField(max_digits=12, decimal_places=3)),
                ('max_units_allowed', models.IntegerField()),
                ('effective_start_timestamp', models.DateTimeField()),
                ('effective_end_timestamp', models.DateTimeField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='orderableproducthistory',
            unique_together=set([('domain', 'code')]),
        ),
        migrations.AlterUniqueTogether(
            name='orderableproduct',
            unique_together=set([('domain', 'code')]),
        ),
        migrations.AlterUniqueTogether(
            name='emergencyorderpackage',
            unique_together=set([('order', 'package_number')]),
        ),
        migrations.AlterIndexTogether(
            name='emergencyorderpackage',
            index_together=set([('order', 'package_number')]),
        ),
        migrations.RenameField(
            model_name='emergencyorder',
            old_name='canceled_status',
            new_name='cancelled_status',
        ),
        migrations.RenameField(
            model_name='emergencyorder',
            old_name='total_vehicles',
            new_name='total_packages',
        ),
        migrations.RenameField(
            model_name='emergencyorderstatusupdate',
            old_name='vehicle_number',
            new_name='package_number',
        ),
        migrations.AddField(
            model_name='emergencyorderstatusupdate',
            name='eta',
            field=models.TimeField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorderstatusupdate',
            name='eta_minutes_remaining',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorderstatusupdate',
            name='package_id',
            field=models.CharField(max_length=126, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='emergencyorder',
            name='status',
            field=models.CharField(default=b'pending', max_length=126),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='emergencyorderstatusupdate',
            index_together=set([('order', 'package_number')]),
        ),
    ]
