from datetime import datetime
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.util.timezones.utils import get_timezone_for_user
from couchexport.models import Format
from custom.openclinica.const import (
    AUDIT_LOGS,
    CC_STUDY_SUBJECT_ID,
    CC_SUBJECT_KEY,
    CC_SUBJECT_CASE_TYPE,
    CC_ENROLLMENT_DATE,
    CC_SEX,
    CC_DOB,
)
from custom.openclinica.models import Subject
from custom.openclinica.utils import get_study_constant, originals_first


class OdmExportReportView(GenericReportView):
    """
    An XML-based export report for OpenClinica integration

    ODM details: http://www.cdisc.org/odm
    OpenClinica: https://docs.openclinica.com/3.1/technical-documents/openclinica-and-cdisc-odm-specifications
    """
    exportable = True
    emailable = False
    asynchronous = True
    name = "ODM Export"
    slug = "odm_export"

    export_format_override = Format.CDISC_ODM

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        super(OdmExportReportView, self).__init__(request, base_context, domain, **kwargs)

        tz = get_timezone_for_user(None, self.domain)
        now = datetime.now(tz)
        file_oid = now.strftime('CommCare_%Y%m%d%H%M%S%z')
        utc_offset = now.strftime('%z')
        with_colon = ':'.join((utc_offset[:-2], utc_offset[-2:]))  # Change UTC offset from "+0200" to "+02:00"
        self.study_details = {
            'file_oid': file_oid,
            'file_description': 'Data imported from CommCare',
            'creation_datetime': now.strftime('%Y-%m-%dT%H:%M:%S') + with_colon,
            'study_name': get_study_constant(domain, 'study_name'),
            'study_description': get_study_constant(domain, 'study_description'),
            'protocol_name': get_study_constant(domain, 'protocol_name'),
            'study_oid': get_study_constant(domain, 'study_oid'),
            'audit_logs': AUDIT_LOGS,
        }

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Subject Key'),
            DataTablesColumn('Study Subject ID'),
            DataTablesColumn('Enrollment Date'),
            DataTablesColumn('Sex'),
            DataTablesColumn('Date of Birth'),
            DataTablesColumn('Events'),
        )

    def subject_headers(self):
        raise NotImplementedError

    def subject_export_rows(self):
        raise NotImplementedError

    @property
    def export_table(self):
        """
        Returns a multi-dimensional list formatted as export_from_tables would expect. It includes all context
        (study data and subjects) required to render an ODM document.
        """
        return [
            [
                'study',  # The first "sheet" is the study details. It has only one row.
                [self.study_details.keys(), self.study_details.values()]
            ],
            [
                'subjects',
                [self.subject_headers()] + list(self.subject_export_rows())
            ]
        ]


class OdmExportReport(OdmExportReportView, CustomProjectReport, CaseListMixin):

    @property
    def rows(self):
        for subject in self.subject_rows():
            row = [
                subject.subject_key,  # What OpenClinica refers to as Person ID; i.e. OID with the "SS_" prefix
                subject.study_subject_id,
                subject.enrollment_date,
                subject.sex,
                subject.dob,
                subject.get_report_events(),
            ]
            yield row

    def get_study_subject_cases(self):
        cases = (CommCareCase.wrap(res['_source']) for res in self.es_results['hits'].get('hits', []))
        for case in cases:
            if case.type != CC_SUBJECT_CASE_TYPE:
                # Skip cases that are not subjects.
                continue
            if not (hasattr(case, CC_SUBJECT_KEY) and hasattr(case, CC_STUDY_SUBJECT_ID)):
                # Skip subjects that have not been selected for the study
                continue
            yield case

    def subject_headers(self):
        return [
            # odm_export_subject.xml expects these to be subject attributes
            'subject_key',
            'study_subject_id',
            'events'
        ]

    def subject_rows(self):
        audit_log_id_ref = {'id': 0}  # To exclude audit logs, set `custom.openclinica.const.AUDIT_LOGS = False`
        for case in self.get_study_subject_cases():
            subject = Subject(getattr(case, CC_SUBJECT_KEY), getattr(case, CC_STUDY_SUBJECT_ID), self.domain)
            subject.enrollment_date = getattr(case, CC_ENROLLMENT_DATE, None)
            subject.sex = getattr(case, CC_SEX, None)
            subject.dob = getattr(case, CC_DOB, None)
            for form in originals_first(case.get_forms()):
                # Pass audit log ID by reference to increment it for each audit log
                subject.add_data(form.form, form, audit_log_id_ref)
            yield subject

    def subject_export_rows(self):
        """
        Rows to appear in the "Subjects" sheet of export_table().

        CdiscOdmExportWriter will render this using the odm_export.xml template to combine subjects into a single
        ODM XML document.
        """
        for subject in self.subject_rows():
            row = [
                'SS_' + subject.subject_key,  # OpenClinica prefixes subject key with "SS_" to make the OID
                subject.study_subject_id,
                subject.get_export_data(),
            ]
            yield row
