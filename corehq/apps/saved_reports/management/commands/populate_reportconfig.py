from dimagi.utils.dates import force_to_date

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return None

    @classmethod
    def couch_doc_type(self):
        return 'ReportConfig'

    @classmethod
    def sql_class(self):
        from corehq.apps.saved_reports.models.ReportConfig import SQLReportConfig
        return SQLReportConfig

    @classmethod
    def commit_adding_migration(cls):
        return "TODO: add once the PR adding this file is merged"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "domain": doc.get("domain"),
                "report_type": doc.get("report_type"),
                "report_slug": doc.get("report_slug"),
                "subreport_slug": doc.get("subreport_slug"),
                "name": doc.get("name"),
                "description": doc.get("description"),
                "owner_id": doc.get("owner_id"),
                "filters": doc.get("filters"),
                "date_range": doc.get("date_range"),
                "days": doc.get("days"),
                "start_date": force_to_date(doc.get("start_date")),
                "end_date": force_to_date(doc.get("end_date")),
                "datespan_slug": doc.get("datespan_slug"),
                "update_seq": doc.get("update_seq"),
                "purge_seq": doc.get("purge_seq"),
                "compact_running": doc.get("compact_running"),
                "db_name": doc.get("db_name"),
                "doc_del_count": doc.get("doc_del_count"),
                "instance_start_time": doc.get("instance_start_time"),
                "disk_size": doc.get("disk_size"),
                "sizes": doc.get("sizes"),
                "doc_count": doc.get("doc_count"),
                "disk_format_version": doc.get("disk_format_version"),
                "other": doc.get("other"),
                "cluster": doc.get("cluster"),
                "data_size": doc.get("data_size"),
            })
        return (model, created)