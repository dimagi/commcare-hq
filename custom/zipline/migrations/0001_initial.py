# -*- coding: utf-8 -*-

from django.db import models, migrations
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmergencyOrder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126)),
                ('requesting_user_id', models.CharField(max_length=126)),
                ('requesting_phone_number', models.CharField(max_length=126)),
                ('location_code', models.CharField(max_length=126)),
                ('products_requested', jsonfield.fields.JSONField(default=dict)),
                ('products_delivered', jsonfield.fields.JSONField(default=dict)),
                ('products_confirmed', jsonfield.fields.JSONField(default=dict)),
                ('timestamp', models.DateTimeField()),
                ('total_vehicles', models.IntegerField(null=True)),
                ('zipline_request_attempts', models.IntegerField(default=0)),
                ('status', models.CharField(default=b'PENDING', max_length=126)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EmergencyOrderStatusUpdate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField()),
                ('zipline_timestamp', models.DateTimeField(null=True)),
                ('status', models.CharField(max_length=126)),
                ('additional_text', models.TextField(null=True)),
                ('vehicle_number', models.IntegerField(null=True)),
                ('vehicle_id', models.CharField(max_length=126, null=True)),
                ('products', jsonfield.fields.JSONField(default=dict)),
                ('order', models.ForeignKey(to='zipline.EmergencyOrder', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterIndexTogether(
            name='emergencyorderstatusupdate',
            index_together=set([('order', 'vehicle_number')]),
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='approved_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='canceled_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='confirmed_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='delivered_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='dispatched_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='location',
            field=models.ForeignKey(to='locations.SQLLocation', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='received_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emergencyorder',
            name='rejected_status',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='zipline.EmergencyOrderStatusUpdate', null=True),
            preserve_default=True,
        ),
    ]
