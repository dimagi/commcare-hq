#Static Definitions of ES mappings.
#In practice the base ES mapping definition for our core type should not change much and shouldn't surprise us if we made subtle changes to it.
#as such, any changes must be done and committed to source control.
#to regenerate case mappings, call the management command ptop_generate_mapping casexml.apps.case.models.CommCareCase
#it'll dump out a json string which you set to here.


#staging
#CASE_INDEX = "hqcases_58bb9e522b9b6513e64cc6e69556c37b"
#prod
#CASE_INDEX = "hqcases_3f765bd72c844d353619408862556ebd"


NULL_VALUE = "__NULL__"
