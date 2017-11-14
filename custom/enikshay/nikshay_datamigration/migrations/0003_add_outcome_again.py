# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nikshay_datamigration', '0002_delete_outcome_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('PatientId', models.OneToOneField(primary_key=True, serialize=False, to='nikshay_datamigration.PatientDetail', on_delete=models.CASCADE)),
                ('Outcome', models.CharField(max_length=255, choices=[(b'NULL', b'NULL'), (b'0', b'0'), (b'1', b'1'), (b'2', b'2'), (b'3', b'3'), (b'4', b'4'), (b'5', b'5'), (b'6', b'6'), (b'7', b'7')])),
                ('OutcomeDate', models.CharField(max_length=255, null=True)),
                ('MO', models.CharField(max_length=255, null=True)),
                ('XrayEPTests', models.CharField(max_length=255, choices=[(b'NULL', b'NULL')])),
                ('MORemark', models.CharField(max_length=255, null=True)),
                ('HIVStatus', models.CharField(max_length=255, null=True, choices=[(b'NULL', b'NULL'), (b'Pos', b'Pos'), (b'Neg', b'Neg'), (b'Unknown', b'Unknown')])),
                ('HIVTestDate', models.CharField(max_length=255, null=True)),
                ('CPTDeliverDate', models.CharField(max_length=255, null=True)),
                ('ARTCentreDate', models.CharField(max_length=255, null=True)),
                ('InitiatedOnART', models.IntegerField(null=True, choices=[(0, 0), (1, 1)])),
                ('InitiatedDate', models.CharField(max_length=255, null=True)),
                ('userName', models.CharField(max_length=255)),
                ('loginDate', models.DateTimeField()),
                ('OutcomeDate1', models.CharField(max_length=255)),
            ],
        ),
    ]
