# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rch', '0003_auto_20170129_1918'),
    ]

    operations = [
        migrations.AddField(
            model_name='rchchild',
            name='BCG_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Birth_Certificate_Number',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Birth_place',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Case_closure',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Child_EID',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Child_MCTS_ID_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPT1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPT2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPT3_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPTBooster1_Complentary_Feeding_Month',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPTBooster1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPTBooster1_Visit_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DPTBooster2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DeathDate',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='DeathPlace',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Death_reason',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Entry_Type',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='HepatitisB0_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='HepatitisB1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='HepatitisB2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='HepatitisB3_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='JE1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='JE2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Landline_no',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='MDDS_StateID',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='MMR_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='MR_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Measles1_Complentary_Feeding_Month',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Measles1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Measles1_Visit_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Measles2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Mother_MCTS_ID_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='OPV0_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='OPV1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='OPV2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='OPV3_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='OPVBooster_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC1_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC2_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC3_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC4_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC5_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC6_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_DangerSign_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_Date_Infant',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_Infant_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_No_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_ReferralFacility_Infant',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='PNC7_Type_Infant',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Penta1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Penta2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Penta3_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Reason_closure',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Rota_Virus_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='Typhoid_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose1_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose2_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose3_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose4_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose5_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose6_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose7_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose8_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchchild',
            name='VitA_Dose9_Dt',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_BP_Distolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_BP_Systolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_FA_Given',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Hb_gm',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_IFA_Given',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Pregnancy_Week',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Referal_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Referal_Facility',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Referal_FacilityName',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Symptoms_High_Risk',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC1_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2_BP_Distolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2_BP_Systolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2_Hb_gm',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2_Pregnancy_Week',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC2_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4_BP_Distolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4_BP_Systolic',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4_Hb_gm',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4_Pregnancy_Week',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ANC4_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='AbortionDate',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Abortion_Preg_Weeks',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Abortion_Type',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Blood_Group',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Death_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='DeletedOn',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Delivery_Place',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Hus_IFSC_Code',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Husband_Enrollment_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='ID_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Induced_Indicate_Facility',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant1_Term',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Breast_Feeding',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Resucitation_Done',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Term',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant2_Weight',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant3_Id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant3_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant3_Resucitation_Done',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant4_Id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant4_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant4_Resucitation_Done',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant5_Id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant5_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant5_Resucitation_Done',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant6_Id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant6_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Infant6_Resucitation_Done',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='JSY_Paid_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Landline_no',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='MDDS_StateID',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Mother_Death_Date',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Mother_Death_Place',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='Mother_Death_Reason',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC1_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC2_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC3_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC4_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC5_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC6_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_DangerSign_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_Date',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_IFA_Tab',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_PPC',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_ReferralFacility_Mother',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PNC7_Type',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PW_Account_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PW_Bank_Name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PW_Enrollment_No',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PW_Enrollment_Time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='PW_IFSC_Code',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='TT2',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='rchmother',
            name='TTB',
            field=models.DateTimeField(null=True),
        ),
    ]
