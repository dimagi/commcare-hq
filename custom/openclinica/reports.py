from __future__ import absolute_import
from datetime import datetime
from casexml.apps.case.models import CommCareCase
from corehq import toggles
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.elastic import SIZE_LIMIT
from corehq.util.timezones.utils import get_timezone_for_user
from couchexport.models import Format
from custom.openclinica.const import (
    AUDIT_LOGS,
    CC_STUDY_SUBJECT_ID,
    CC_SUBJECT_KEY,
    CC_SUBJECT_CASE_TYPE,
)
from custom.openclinica.models import Subject
from custom.openclinica.utils import get_study_constant


class OdmExportReport(ProjectReport, CaseListMixin, GenericReportView):
    """
    An XML-based export report for OpenClinica integration

    ODM details: http://www.cdisc.org/odm
    OpenClinica: https://docs.openclinica.com/3.1/technical-documents/openclinica-and-cdisc-odm-specifications
    """
    exportable = True
    exportable_all = True
    emailable = True
    asynchronous = True
    name = "Clinical Study Data"
    slug = "odm_export"

    export_format_override = Format.CDISC_ODM

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain and toggles.OPENCLINICA.enabled(domain)

    @property
    def headers(self):
        # These match the values returned by rows()
        return DataTablesHeader(
            DataTablesColumn('Subject Key'),
            DataTablesColumn('Study Subject ID'),
            DataTablesColumn('Enrollment Date'),
            DataTablesColumn('Sex'),
            DataTablesColumn('Date of Birth'),
            DataTablesColumn('Events'),
        )

    @staticmethod
    def subject_headers():
        # These match the values returned by get_all_rows()
        return [
            'subject_key',
            'study_subject_id',
            'enrollment_date',
            'sex',
            'dob',
            'events'
        ]

    @property
    def export_table(self):
        """
        Returns a multi-dimensional list formatted as export_from_tables would expect. It includes all context
        (study data and subjects) required to render an ODM document.
        """
        tz = get_timezone_for_user(None, self.domain)
        now = datetime.now(tz)
        file_oid = now.strftime('CommCare_%Y%m%d%H%M%S%z')
        utc_offset = now.strftime('%z')
        with_colon = ':'.join((utc_offset[:-2], utc_offset[-2:]))  # Change UTC offset from "+0200" to "+02:00"
        study_details = {
            'file_oid': file_oid,
            'file_description': 'Data imported from CommCare',
            'creation_datetime': now.strftime('%Y-%m-%dT%H:%M:%S') + with_colon,
            'study_name': get_study_constant(self.domain, 'study_name'),
            'study_description': get_study_constant(self.domain, 'study_description'),
            'protocol_name': get_study_constant(self.domain, 'protocol_name'),
            'study_oid': get_study_constant(self.domain, 'study_oid'),
            'audit_logs': AUDIT_LOGS,
            # The template accepts XML strings in params "study_xml" and
            # "admin_data_xml" which come from the study metadata.
            'study_xml': get_study_constant(self.domain, 'study_xml'),
            'admin_data_xml': get_study_constant(self.domain, 'admin_data_xml'),
            'domain': self.domain,
        }
        return [
            [
                'study',  # The first "sheet" is the study details. It has only one row.
                [list(study_details.keys()), list(study_details.values())]
            ],
            [
                'subjects',
                [self.subject_headers()] + list(self.export_rows)
            ]
        ]

    @staticmethod
    def is_subject_selected(case):
        """
        Is the case that of a subject who has been selected for a study
        """
        return (
            case.type == CC_SUBJECT_CASE_TYPE and
            hasattr(case, CC_SUBJECT_KEY) and
            hasattr(case, CC_STUDY_SUBJECT_ID)
        )

    @property
    def rows(self):
        audit_log_id_ref = {'id': 0}  # To exclude audit logs, set `custom.openclinica.const.AUDIT_LOGS = False`
        query = self._build_query().case_type(CC_SUBJECT_CASE_TYPE)
        for result in query.scroll():
            case = CommCareCase.wrap(result)
            if not self.is_subject_selected(case):
                continue
            subject = Subject.wrap(case, audit_log_id_ref)
            row = [
                subject.subject_key,  # What OpenClinica refers to as Person ID; i.e. OID with the "SS_" prefix
                subject.study_subject_id,
                subject.enrollment_date,
                subject.sex,
                subject.dob,
                subject.get_report_events(),
            ]
            yield row

    @property
    def get_all_rows(self):
        """
        Rows to appear in the "Subjects" sheet of export_table().

        CdiscOdmExportWriter will render this using the odm_export.xml template to combine subjects into a single
        ODM XML document.

        The values are also used to register new subjects if the web service is enabled.
        """
        audit_log_id_ref = {'id': 0}  # To exclude audit logs, set `custom.openclinica.const.AUDIT_LOGS = False`
        query = self._build_query().case_type(CC_SUBJECT_CASE_TYPE).start(0).size(SIZE_LIMIT)
        rows = []
        for result in query.scroll():
            case = CommCareCase.wrap(result)
            if not self.is_subject_selected(case):
                continue
            subject = Subject.wrap(case, audit_log_id_ref)
            row = [
                'SS_' + subject.subject_key,  # OpenClinica prefixes subject key with "SS_" to make the OID
                subject.study_subject_id,
                subject.enrollment_date,
                subject.sex,
                subject.dob,
                subject.get_export_data(),
            ]
            rows.append(row)
        return rows
