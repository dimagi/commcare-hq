import logging


class ScheduledReportLogger:
    @staticmethod
    def log_email_success(report, email, body):
        from .models import ScheduledReportLog

        report_length = len(body)
        logging.info(f'Sent email for scheduled report {report._id} to {email}. Details: '
            f'Domain: {report.domain}, bytes: {report_length}')

        ScheduledReportLog.objects.create(
            domain=report.domain,
            report_id=report._id,
            sent_to=email,
            state=ScheduledReportLog.LOG_STATE_SUCCESS,
            size=report_length,
        )

    @staticmethod
    def log_email_failure(report, email, body, exception):
        from .models import ScheduledReportLog

        report_length = len(body)
        logging.error(f'Encountered error while sending report {report._id} to {email}. Details: '
            f'Domain: {report.domain}, bytes: {report_length}. Error: {exception}')

        ScheduledReportLog.objects.create(
            domain=report.domain,
            report_id=report._id,
            sent_to=email,
            state=ScheduledReportLog.LOG_STATE_ERROR,
            size=report_length,
            error=exception
        )

    @staticmethod
    def log_email_size_failure(report, email, emails, body):
        from .models import ScheduledReportLog

        report_length = len(body)
        emails_str = ', '.join(emails)
        logging.info(f'Email for scheduled report {report._id} to {email} failed due to size. Details: '
            f'Domain: {report.domain}, bytes: {report_length}. Attempting to send as attachments to {emails_str}')

        ScheduledReportLog.objects.create(
            domain=report.domain,
            report_id=report._id,
            sent_to=email,
            state=ScheduledReportLog.LOG_STATE_RETRY,
            size=report_length,
            error='size'
        )
