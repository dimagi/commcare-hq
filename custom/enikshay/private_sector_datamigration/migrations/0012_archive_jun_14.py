# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-30 13:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('private_sector_datamigration', '0011_agencyTypeId_nonnull'),
    ]

    operations = [
        migrations.RenameModel('Beneficiary', 'Beneficiary_Jun14'),
        migrations.RenameModel('Episode', 'Episode_Jun14'),
        migrations.RenameModel('Adherence', 'Adherence_Jun14'),
        migrations.RenameModel('EpisodePrescription', 'EpisodePrescription_Jun14'),
        migrations.RenameModel('Voucher', 'Voucher_Jun14'),
        migrations.RenameModel('Agency', 'Agency_Jun14'),
        migrations.RenameModel('UserDetail', 'UserDetail_Jun14'),
    ] + [
        migrations.CreateModel(
            name='Agency_Jun30',
            fields=[
                ('id', models.IntegerField(null=True, unique=True)),
                ('agencyId', models.IntegerField(primary_key=True, serialize=False)),
                ('agencyName', models.CharField(max_length=256, null=True)),
                ('agencyStatus', models.CharField(max_length=256, null=True)),
                ('agencySubTypeId', models.CharField(max_length=256, null=True)),
                ('agencyTypeId', models.CharField(max_length=256)),
                ('associatedFOId', models.CharField(max_length=256, null=True)),
                ('attachedToAgency', models.CharField(max_length=256, null=True)),
                ('creationDate', models.DateTimeField()),
                ('creator', models.CharField(max_length=256, null=True)),
                ('dateOfRegn', models.DateTimeField()),
                ('labOrLcc', models.CharField(max_length=256, null=True)),
                ('modificationDate', models.DateTimeField()),
                ('modifiedBy', models.CharField(max_length=256, null=True)),
                ('nikshayId', models.CharField(max_length=256, null=True)),
                ('nikshayProcessedFlag', models.CharField(max_length=1, null=True)),
                ('onBehalfOf', models.CharField(max_length=256, null=True)),
                ('organisationId', models.IntegerField()),
                ('owner', models.CharField(max_length=256, null=True)),
                ('parentAgencyId', models.IntegerField()),
                ('parentAgencyType', models.CharField(max_length=256, null=True)),
                ('payToParentAgency', models.CharField(max_length=256, null=True)),
                ('pendingApproval', models.CharField(max_length=256, null=True)),
                ('regnIssueAuthId', models.CharField(max_length=256, null=True)),
                ('regnNumber', models.CharField(max_length=256, null=True)),
                ('sendAlert', models.CharField(max_length=256, null=True)),
                ('subOrganisationId', models.IntegerField()),
                ('tbDrugInStock', models.CharField(max_length=256, null=True)),
                ('tbTests', models.CharField(max_length=256, null=True)),
                ('trainingAttended', models.CharField(max_length=256, null=True)),
                ('tbCorner', models.CharField(max_length=1, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Beneficiary_Jun30',
            fields=[
                ('id', models.IntegerField(null=True)),
                ('additionalDetails', models.CharField(max_length=500, null=True)),
                ('addressLineOne', models.CharField(max_length=256, null=True)),
                ('addressLineTwo', models.CharField(max_length=256, null=True)),
                ('age', models.IntegerField(null=True)),
                ('alertFrequency', models.CharField(max_length=60, null=True)),
                ('associatedFOId', models.CharField(max_length=10, null=True)),
                ('associatedQPId', models.CharField(max_length=10, null=True)),
                ('blockOrHealthPostId', models.CharField(max_length=10, null=True)),
                ('caseCreatedBy', models.CharField(max_length=10, null=True)),
                ('caseId', models.CharField(max_length=18, primary_key=True, serialize=False)),
                ('caseName', models.CharField(max_length=62, null=True)),
                ('caseReferredBy', models.CharField(max_length=18, null=True)),
                ('caseStatus', models.CharField(max_length=20, null=True)),
                ('configureAlert', models.CharField(max_length=5, null=True)),
                ('creationDate', models.DateTimeField()),
                ('creator', models.CharField(max_length=255, null=True)),
                ('dateOfIdentification', models.DateTimeField(null=True)),
                ('dateOfRegn', models.DateTimeField()),
                ('diagnosisBasisId', models.IntegerField(null=True)),
                ('districtId', models.CharField(max_length=6, null=True)),
                ('dob', models.DateTimeField(null=True)),
                ('email', models.CharField(max_length=6, null=True)),
                ('emergencyContactNo', models.CharField(max_length=10, null=True)),
                ('extraPulmonarySiteId', models.IntegerField(null=True)),
                ('fatherHusbandName', models.CharField(max_length=60, null=True)),
                ('firstName', models.CharField(max_length=30)),
                ('gender', models.CharField(max_length=10, null=True)),
                ('identificationNumber', models.CharField(max_length=30, null=True)),
                ('identificationTypeId', models.CharField(max_length=10, null=True)),
                ('isActive', models.CharField(max_length=10, null=True)),
                ('languagePreferences', models.CharField(max_length=30, null=True)),
                ('lastName', models.CharField(max_length=30)),
                ('mdrTBSuspected', models.CharField(max_length=30, null=True)),
                ('middleName', models.CharField(max_length=30, null=True)),
                ('modificationDate', models.DateTimeField(null=True)),
                ('modifiedBy', models.CharField(max_length=255, null=True)),
                ('nikshayId', models.CharField(max_length=10, null=True)),
                ('occupation', models.CharField(max_length=30, null=True)),
                ('onBehalfOf', models.CharField(max_length=10, null=True)),
                ('organisationId', models.IntegerField()),
                ('owner', models.CharField(max_length=255, null=True)),
                ('patientCategoryId', models.IntegerField(null=True)),
                ('phoneNumber', models.CharField(max_length=10)),
                ('pincode', models.IntegerField(null=True)),
                ('provisionalDiagnosis', models.CharField(max_length=255, null=True)),
                ('qpReferralBy', models.CharField(max_length=10, null=True)),
                ('qpReferralConfirmationStatus', models.CharField(max_length=20, null=True)),
                ('referredQP', models.CharField(max_length=10, null=True)),
                ('rifampicinResistanceId', models.IntegerField(null=True)),
                ('rxPreferences', models.CharField(max_length=255, null=True)),
                ('shiftedToCATIVMdr', models.CharField(max_length=5, null=True)),
                ('siteOfDiseaseId', models.IntegerField(null=True)),
                ('stateId', models.CharField(max_length=10, null=True)),
                ('subOrganizationId', models.IntegerField(null=True)),
                ('symptoms', models.CharField(max_length=255, null=True)),
                ('tbCategoryId', models.IntegerField(null=True)),
                ('testToBeConducted', models.CharField(max_length=255, null=True)),
                ('tsAccountTypeId', models.CharField(max_length=6, null=True)),
                ('tsBankAccNo', models.BigIntegerField(null=True)),
                ('tsBankAccountName', models.CharField(max_length=100, null=True)),
                ('tsBankBranch', models.CharField(max_length=100, null=True)),
                ('tsBankIFSCCode', models.CharField(max_length=11, null=True)),
                ('tsBankMicrCode', models.BigIntegerField(null=True)),
                ('tsBankName', models.CharField(max_length=100, null=True)),
                ('tsId', models.CharField(max_length=10, null=True)),
                ('tsPhoneNo', models.CharField(max_length=10, null=True)),
                ('tsType', models.CharField(max_length=20, null=True)),
                ('tsprovidertype', models.CharField(max_length=30, null=True)),
                ('villageTownCity', models.CharField(max_length=60, null=True)),
                ('wardId', models.CharField(max_length=10, null=True)),
                ('physicalCaseId', models.CharField(max_length=18, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Episode_Jun30',
            fields=[
                ('id', models.IntegerField(null=True)),
                ('accountName', models.CharField(max_length=255, null=True)),
                ('accountType', models.CharField(max_length=255, null=True)),
                ('adherenceScore', models.DecimalField(decimal_places=10, max_digits=14)),
                ('alertFrequencyId', models.IntegerField()),
                ('associatedFO', models.CharField(max_length=255, null=True)),
                ('bankName', models.CharField(max_length=255, null=True)),
                ('basisOfDiagnosis', models.CharField(max_length=255, null=True)),
                ('beneficiaryID', models.CharField(db_index=True, max_length=18)),
                ('branchName', models.CharField(max_length=255, null=True)),
                ('creationDate', models.DateTimeField(null=True)),
                ('creator', models.CharField(max_length=255, null=True)),
                ('dateOfDiagnosis', models.DateTimeField()),
                ('diabetes', models.CharField(max_length=255, null=True)),
                ('dstStatus', models.CharField(max_length=255, null=True)),
                ('episodeDisplayID', models.IntegerField(db_index=True)),
                ('episodeID', models.CharField(max_length=8, primary_key=True, serialize=False)),
                ('extraPulmonary', models.CharField(max_length=255, null=True)),
                ('hiv', models.CharField(max_length=255, null=True)),
                ('ifscCode', models.CharField(max_length=255, null=True)),
                ('isNonSuperVisor', models.CharField(max_length=255, null=True)),
                ('lastMonthAdherencePct', models.DecimalField(decimal_places=10, max_digits=14)),
                ('lastTwoWeeksAdherencePct', models.DecimalField(decimal_places=10, max_digits=14)),
                ('micr', models.CharField(max_length=255, null=True)),
                ('missedDosesPct', models.DecimalField(decimal_places=10, max_digits=14)),
                ('mobileNumber', models.CharField(max_length=255, null=True)),
                ('modificationDate', models.DateTimeField(null=True)),
                ('modifiedBy', models.CharField(max_length=255, null=True)),
                ('name', models.CharField(max_length=255, null=True)),
                ('newOrRetreatment', models.CharField(max_length=255, null=True)),
                ('nikshayBy', models.CharField(max_length=255, null=True)),
                ('nikshayID', models.CharField(max_length=18, null=True)),
                ('nonRxSupervisorName', models.CharField(max_length=255, null=True)),
                ('onBeHalfOf', models.CharField(max_length=10, null=True)),
                ('organisationId', models.CharField(max_length=18, null=True)),
                ('owner', models.CharField(max_length=255, null=True)),
                ('patientWeight', models.DecimalField(decimal_places=10, max_digits=40)),
                ('phoneNumber', models.CharField(max_length=255, null=True)),
                ('retreatmentReason', models.CharField(max_length=255, null=True)),
                ('rxArchivalDate', models.DateTimeField(null=True)),
                ('rxAssignedBy', models.CharField(max_length=255, null=True)),
                ('rxInitiationStatus', models.CharField(max_length=255, null=True)),
                ('rxOutcomeDate', models.DateTimeField(null=True)),
                ('rxStartDate', models.DateTimeField()),
                ('rxSupervisor', models.CharField(max_length=255, null=True)),
                ('site', models.CharField(max_length=255)),
                ('status', models.CharField(max_length=255, null=True)),
                ('treatingQP', models.CharField(max_length=255, null=True)),
                ('treatmentOutcomeId', models.CharField(max_length=255, null=True)),
                ('treatmentPhase', models.CharField(max_length=255, null=True)),
                ('tsProviderType', models.CharField(max_length=255, null=True)),
                ('unknownAdherencePct', models.DecimalField(decimal_places=10, max_digits=14)),
                ('unresolvedMissedDosesPct', models.DecimalField(decimal_places=10, max_digits=14)),
                ('treatingHospital', models.CharField(max_length=10, null=True)),
                ('treatmentCompletionInsentiveFlag', models.CharField(max_length=1, null=True)),
                ('mermIMIEno', models.CharField(max_length=255, null=True)),
                ('adherenceSupportAssigned', models.CharField(max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='EpisodePrescription_Jun30',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('adultOrPaediatric', models.CharField(max_length=255, null=True)),
                ('beneficiaryId', models.CharField(db_index=True, max_length=18, null=True)),
                ('creationDate', models.DateTimeField()),
                ('creator', models.CharField(max_length=255, null=True)),
                ('dosageStrength', models.CharField(max_length=255, null=True)),
                ('episodeId', models.CharField(max_length=8, null=True)),
                ('modificationDate', models.DateTimeField(null=True)),
                ('modifiedBy', models.CharField(max_length=255, null=True)),
                ('next_refill_date', models.DateTimeField(null=True)),
                ('numberOfDays', models.IntegerField()),
                ('numberOfDaysPrescribed', models.CharField(max_length=255)),
                ('numberOfRefill', models.CharField(max_length=255, null=True)),
                ('owner', models.CharField(max_length=255, null=True)),
                ('presUnits', models.CharField(max_length=255, null=True)),
                ('prescStatus', models.CharField(max_length=255, null=True)),
                ('prescriptionID', models.IntegerField()),
                ('pricePerUnit', models.DecimalField(decimal_places=10, max_digits=14)),
                ('pricePerUnits', models.CharField(max_length=255, null=True)),
                ('productID', models.IntegerField()),
                ('productName', models.CharField(max_length=255, null=True)),
                ('refill_Index', models.IntegerField()),
                ('typicalUnits', models.CharField(max_length=255, null=True)),
                ('unitDesc', models.CharField(max_length=255, null=True)),
                ('voucherID', models.IntegerField()),
                ('voucherStatus', models.CharField(max_length=255, null=True)),
                ('motechUserName', models.CharField(max_length=255, null=True)),
                ('physicalVoucherNumber', models.CharField(max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserDetail_Jun30',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('accountTypeId', models.CharField(max_length=256, null=True)),
                ('addressLineOne', models.CharField(max_length=256, null=True)),
                ('addressLineTwo', models.CharField(max_length=256, null=True)),
                ('agencyId', models.IntegerField()),
                ('alternateMobileNumber', models.CharField(max_length=256, null=True)),
                ('alternateMobileNumber1', models.CharField(max_length=256, null=True)),
                ('alternateMobileNumber2', models.CharField(max_length=256, null=True)),
                ('bankAccountName', models.CharField(max_length=256, null=True)),
                ('bankAccountNumber', models.CharField(max_length=256, null=True)),
                ('bankBranch', models.CharField(max_length=256, null=True)),
                ('bankIFSCCode', models.CharField(max_length=256, null=True)),
                ('bankName', models.CharField(max_length=256, null=True)),
                ('blockOrHealthPostId', models.CharField(max_length=256, null=True)),
                ('creationDate', models.DateTimeField(null=True)),
                ('creator', models.CharField(max_length=256, null=True)),
                ('districtId', models.CharField(max_length=256, null=True)),
                ('dob', models.DateTimeField(null=True)),
                ('email', models.CharField(max_length=256, null=True)),
                ('firstName', models.CharField(max_length=256, null=True)),
                ('gender', models.CharField(max_length=256, null=True)),
                ('isPasswordResetFlag', models.NullBooleanField()),
                ('isPrimary', models.BooleanField()),
                ('landLineNumber', models.CharField(max_length=256, null=True)),
                ('lastName', models.CharField(max_length=256, null=True)),
                ('latitude', models.CharField(max_length=256, null=True)),
                ('longitude', models.CharField(max_length=256, null=True)),
                ('micrCode', models.IntegerField(null=True)),
                ('middleName', models.CharField(max_length=256, null=True)),
                ('mobileNumber', models.CharField(max_length=256, null=True)),
                ('modificationDate', models.DateTimeField(null=True)),
                ('modifiedBy', models.CharField(max_length=256, null=True)),
                ('motechUserName', models.CharField(max_length=256, unique=True)),
                ('organisationId', models.IntegerField()),
                ('owner', models.CharField(max_length=256, null=True)),
                ('passwordResetFlag', models.BooleanField()),
                ('pincode', models.IntegerField()),
                ('stateId', models.CharField(max_length=256, null=True)),
                ('status', models.CharField(max_length=256, null=True)),
                ('subOrganisationId', models.IntegerField()),
                ('tuId', models.CharField(max_length=256, null=True)),
                ('uniqIDNo', models.CharField(max_length=256, null=True)),
                ('uniqIDType', models.CharField(max_length=256, null=True)),
                ('userId', models.IntegerField()),
                ('userName', models.CharField(max_length=256, null=True)),
                ('valid', models.BooleanField()),
                ('villageTownCity', models.CharField(max_length=256, null=True)),
                ('wardId', models.CharField(max_length=256, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Voucher_Jun30',
            fields=[
                ('id', models.BigIntegerField()),
                ('caseId', models.CharField(max_length=18, null=True)),
                ('comments', models.CharField(max_length=512, null=True)),
                ('creationDate', models.DateTimeField()),
                ('creator', models.CharField(max_length=255, null=True)),
                ('episodeId', models.CharField(max_length=8, null=True)),
                ('issuedAmount', models.CharField(max_length=255, null=True)),
                ('labId', models.CharField(max_length=255, null=True)),
                ('labTestId', models.CharField(max_length=255, null=True)),
                ('modificationDate', models.DateTimeField()),
                ('modifiedBy', models.CharField(max_length=255, null=True)),
                ('owner', models.CharField(max_length=255, null=True)),
                ('pharmacyId', models.CharField(max_length=255, null=True)),
                ('prescriptionId', models.CharField(max_length=255, null=True)),
                ('validationModeId', models.CharField(max_length=255, null=True)),
                ('voucherAmount', models.CharField(max_length=255, null=True)),
                ('voucherCreatedDate', models.DateTimeField()),
                ('voucherGeneratedBy', models.CharField(max_length=255, null=True)),
                ('voucherLastUpdateDate', models.DateTimeField(null=True)),
                ('voucherNumber', models.BigIntegerField(primary_key=True, serialize=False)),
                ('voucherStatusId', models.CharField(max_length=255, null=True)),
                ('voucherTypeId', models.CharField(max_length=255, null=True)),
                ('agencyName', models.CharField(max_length=255, null=True)),
                ('voucherCancelledDate', models.DateTimeField(null=True)),
                ('voucherExpiredDate', models.DateTimeField(null=True)),
                ('voucherValidatedDate', models.DateTimeField(null=True)),
                ('voucherUsedDate', models.DateTimeField(null=True)),
                ('physicalVoucherNumber', models.CharField(max_length=255, null=True)),
                ('markedUpVoucherAmount', models.CharField(max_length=255, null=True)),
                ('voucherAmountSystem', models.CharField(max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Adherence_Jun30',
            fields=[
                ('id', models.IntegerField(null=True)),
                ('adherenceId', models.CharField(max_length=18, primary_key=True, serialize=False)),
                ('beneficiaryId', models.ForeignKey(null=True, on_delete=models.deletion.CASCADE, to='private_sector_datamigration.Beneficiary_Jun30')),
                ('commentId', models.CharField(max_length=8, null=True)),
                ('creationDate', models.DateTimeField()),
                ('creator', models.CharField(max_length=255, null=True)),
                ('dosageStatusId', models.IntegerField(db_index=True)),
                ('doseDate', models.DateTimeField()),
                ('doseReasonId', models.IntegerField()),
                ('episodeId', models.CharField(db_index=True, max_length=8)),
                ('modificationDate', models.DateTimeField(null=True)),
                ('modifiedBy', models.CharField(max_length=255, null=True)),
                ('owner', models.CharField(max_length=255, null=True)),
                ('reportingMechanismId', models.IntegerField(db_index=True)),
                ('unknwDoseReasonId', models.CharField(max_length=8, null=True)),
            ],
        ),
    ]
