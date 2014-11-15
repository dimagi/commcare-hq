from custom.tdh.reports.child_consultation_history import ChildConsultationHistoryReport
from custom.tdh.reports.infant_consultation_history import InfantConsultationHistoryReport
from custom.tdh.reports.newborn_consultation_history import NewbornConsultationHistoryReport

TDH_DOMAINS = ('tdhtesting', )

ENROLL_CHILD_XMLNSES = ("http://openrosa.org/formdesigner/10753F54-3ABA-45BA-B2B4-3AFE7F558682", )
INFANT_CLASSIFICATION_XMLNSES = ("http://openrosa.org/formdesigner/B70118AE-67BB-424E-8873-901C65ED748F", )
NEWBORN_CLASSIFICATION_XMLNSES = ("http://openrosa.org/formdesigner/BEFAA61E-C03D-4641-9EAE-EA781FF7EF65", )
CHILD_CLASSIFICATION_XMLNSES = ("http://openrosa.org/formdesigner/2f934e7b72944d72fd925e870030ecdc2e5e2ea6", )
INFANT_TREATMENT_XMLNSES = ("http://openrosa.org/formdesigner/604656a56cce6cfe691699123c2e2fe9f077da77", )
NEWBORN_TREATMENT_XMLNSES = ("http://openrosa.org/formdesigner/1904f15bf570b2e0169690416432f6103621b155", )
CHILD_TREATMENT_XMLNSES = ("http://openrosa.org/formdesigner/88885ce54e53952782e0480736cec53bba9e3be7", )

CUSTOM_REPORTS = (
    ('Custom Reports', (
        InfantConsultationHistoryReport,
        NewbornConsultationHistoryReport,
        ChildConsultationHistoryReport
    )),
)
