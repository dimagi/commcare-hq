from datetime import *

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db import connection

from corehq.apps.xforms.models import Metadata, FormDefModel, ElementDefModel, FormDataGroup
# from corehq.apps.domain.models import Membership
# from django.contrib.auth.models import User

from intel.schema_models import *


# dropping roles - HQ is just another clinic.
class Clinic(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = _("Clinic")


# have to join on username, since user_ids are not consistent.
# gods of db design weep for future maintainers :'(
class UserClinic(models.Model):
    username = models.CharField(max_length=255)
    clinic = models.ForeignKey(Clinic, null=True, blank=True)
    is_chw = models.BooleanField(default=False)
    
    def __unicode__(self):
        return "User: %s Clinic: %s" % (self.username, self.clinic.name)

    class Meta:
        verbose_name = _("User Clinic")
        unique_together = ('username', 'clinic')


# this table records clinic visits for mothers.
class ClinicVisit(models.Model):
    mother_name  = models.CharField(max_length=255)
    chw_name    = models.CharField(max_length=255)
    chw_case_id = models.CharField(max_length=255)
    clinic = models.ForeignKey(Clinic)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('mother_name', 'chw_name', 'chw_case_id')


def clinic_visits(clinic_id=None, chw_name=None):
    cv = ClinicVisit.objects.all()
    
    if clinic_id is not None:
        cv = cv.filter(clinic=clinic_id)
    
    if chw_name is not None:
        cv = cv.filter(chw_name=chw_name)
    
    visits = {}
    for v in cv:
        visits["%s-%s-%s" % (v.mother_name, v.chw_name, v.chw_case_id)] = v
    
    return visits
    
# schema specific methods - these use the inspectdb general schema_models.py which in turn dumps the models generated per the domain's xforms
REGISTRATION_TABLE = IntelGrameenMotherRegistration._meta.db_table
FOLLOWUP_TABLE     = IntelGrameenSafeMotherhoodFollowup._meta.db_table

def registrations():
    return IntelGrameenMotherRegistration.objects.exclude(meta_username='admin')

def hi_risk():
    return IntelGrameenMotherRegistration.objects.exclude(meta_username='admin').filter(sampledata_hi_risk="yes")

def follow_up():
    return IntelGrameenSafeMotherhoodFollowup.objects.all()


# this is because we don't use foreign keys properly. 
# TODO: see if Django allows explicitly joining on the query (as we do in registrations_by())
def chws_for(clinic_id):
    chws = []
    for i in Clinic.objects.get(id=clinic_id).userclinic_set.values_list('username', 'is_chw'):
        if i[1]: chws.append(i[0])
    
    return chws

# new
def get_chw_registrations_table(clinic_id = None):   
    rows = []

    userclinics = UserClinic.objects.exclude(id=1).filter(is_chw=True)

    if clinic_id is not None:
        userclinics = userclinics.filter(clinic=clinic_id)

    for uc in userclinics:
        username = uc.username
        rows.append ({
            'name' : username,
            'reg'   : registrations().filter(meta_username=username).count(),
            'risk'  : hi_risk().filter(meta_username=username).count(),
            'follow': follow_up().filter(meta_username=username).count(),
            'visits': len(clinic_visits(chw_name=username)),
            'clinic': uc.clinic.name,
            'clinic_id': uc.clinic.id
        })

    return rows

# def all_chws():
#     chws = []
#     for i in registrations().values('meta_username').distinct():
#         chws.append(i['meta_username'])
#     
#     return chws
# # old
# def get_chw_registrations_table(clinic_id = None):   
#     rows = [] ; cu = {}
#     for i in UserClinic.objects.all(): cu[i.username] = { 'clinic': i.clinic.name, 'clinic_id': i.clinic.id }
# 
#     for chw in all_chws():
#         if clinic_id is not None and cu[chw]['clinic_id'] != clinic_id: continue
#         rows.append ({
#             'name' : chw,
#             'reg'   : registrations().filter(meta_username=chw).count(),
#             'risk'  : hi_risk().filter(meta_username=chw).count(),
#             'follow': follow_up().filter(meta_username=chw).count(),
#             'visits': len(clinic_visits(chw_name=chw)),
#             'clinic': cu[chw]['clinic'],
#             'clinic_id': cu[chw]['clinic_id']
#         })
# 
#     return rows


def attachments_for(view):
    atts = {}
    
    group = FormDataGroup.objects.get(view_name=view)
    
    for a in Metadata.objects.filter(formdefmodel__in = group.forms.all()):
        atts[a.raw_data] = a.attachment

    return atts


def registrations_by(group_by):
    # sampledata_case_id
    sql = ''' 
        SELECT clinic_id, count(*)
        FROM %s, intel_userclinic
        WHERE meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (REGISTRATION_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))


def hi_risk_by(group_by):
    # sampledata_case_id
    sql = ''' 
        SELECT clinic_id, count(*)
        FROM %s, intel_userclinic
        WHERE sampledata_hi_risk = 'yes' and meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (REGISTRATION_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))


def followup_by(group_by):
    # safe_pregnancy_case_id
    sql = ''' 
        SELECT clinic_id, count(*)
        FROM %s, intel_userclinic
        WHERE meta_username = intel_userclinic.username
        GROUP BY %s
    ''' % (FOLLOWUP_TABLE, group_by)
    return _result_to_dict(_rawquery(sql))



def _rawquery(sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

# turns a bunch of 2 value lists to dictionary. Used for group results    
def _result_to_dict(results):
    res = {}
    for row in results:
        res[row[0]] = row[1]

    return res
    
def _date_format(startdate, enddate):
    return startdate.strftime("%Y-%m-%d"), (enddate + timedelta(days=1)).strftime("%Y-%m-%d")
    
    
def clinic_chart_sql(startdate, enddate, clinic_id):
    startdate, enddate = _date_format(startdate, enddate)
    return '''    
        SELECT DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), prof.username, count(*)
        FROM xformmanager_metadata meta,xformmanager_formdefmodel forms, hq_domain domains, intel_userclinic prof, intel_clinic
        WHERE forms.id = meta.formdefmodel_id AND intel_clinic.id = prof.clinic_id AND prof.username = meta.username 
            AND forms.domain_id = domains.id AND domains.name = 'Grameen' AND meta.timeend > '%s' AND meta.timeend < '%s' 
            AND clinic_id = %s
        GROUP BY DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), prof.username, clinic_id
        ORDER BY timeend ASC;
        ''' % (startdate, enddate, clinic_id)
        
    
def hq_chart_sql(startdate, enddate):
    startdate, enddate = _date_format(startdate, enddate)
    return '''    
        SELECT DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), intel_clinic.name as clinic, count(*)
        FROM xformmanager_metadata meta, xformmanager_formdefmodel forms, hq_domain domains, intel_userclinic prof, intel_clinic
        WHERE intel_clinic.id = prof.clinic_id AND prof.username = meta.username AND forms.id = meta.formdefmodel_id
            AND forms.domain_id = domains.id AND domains.name = 'Grameen' AND meta.timeend > '%s' AND meta.timeend < '%s'
        GROUP BY DATE_FORMAT(timeend,'%%%%m/%%%%d/%%%%Y'), clinic
        ORDER BY timeend ASC;
        ''' % (startdate, enddate)


def hq_risk_sql(clinic_id):
    return '''
        SELECT 
            COUNT(NULLIF(sampledata_hi_risk,'no')) AS high_risk,
            COUNT(NULLIF(sampledata_mother_height,'over_150')) AS small_frame,
            COUNT(NULLIF(sampledata_previous_csection,'no')) AS previous_c_section,
            COUNT(NULLIF(sampledata_previous_newborn_death,'no')) AS previous_newborn_death,
            COUNT(NULLIF(sampledata_previous_bleeding,'no')) AS previous_bleeding,
            COUNT(NULLIF(sampledata_heart_problems,'no')) AS heart_problems,
            COUNT(NULLIF(sampledata_diabetes,'no')) AS diabetes,
            COUNT(NULLIF(sampledata_hip_problems,'no')) AS hip_problems,
            COUNT(NULLIF(sampledata_card_results_syphilis_result,'negative')) AS syphilis,
            COUNT(NULLIF(sampledata_card_results_hepb_result,'negative')) AS hebp,
            COUNT(NULLIF(sampledata_over_5_years,'no')) AS time_since_last,
            COUNT(NULLIF(sampledata_card_results_hb_test,'normal')) AS low_hemoglobin,
            COUNT(IF(sampledata_mother_age <= 18, 1, NULL)) AS age_under_19,
            COUNT(IF(sampledata_mother_age >= 34, 1, NULL)) AS age_over_34,
            COUNT(IF(sampledata_previous_terminations >= 3, 1, NULL)) AS over_3_terminations,
            COUNT(IF(sampledata_previous_pregnancies >= 5, 1, NULL)) AS over_5_pregs, 
            COUNT(
                NULLIF(sampledata_card_results_blood_group, 'opositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'apositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'abpositive') 
                OR NULLIF(sampledata_card_results_blood_group, 'bpositive')) AS rare_blood
        FROM %s, intel_userclinic 
        WHERE meta_username = intel_userclinic.username AND meta_username <> 'admin' AND intel_userclinic.clinic_id = %s;
        ''' % (REGISTRATION_TABLE, clinic_id)
