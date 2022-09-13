import json
from uuid import UUID

from django.db.models import Q

from dimagi.utils.chunked import chunked

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import (
    DiffDocs,
    PopulateSQLCommand,
)


class PopulateLookupTableCommand(PopulateSQLCommand):

    def handle(self, *, chunk_size, fixup_diffs, **kw):
        self._id_sets_only_in_sql = []
        result = super().handle(chunk_size=chunk_size, fixup_diffs=fixup_diffs, **kw)
        if fixup_diffs:
            with self.open_log(self.log_path, "a") as logfile:
                self.delete_rows_only_in_sql(fixup_diffs, logfile, chunk_size)
        return result

    def _verify_docs(self, docs, logfile, verify_only):
        super()._verify_docs(docs, logfile, verify_only)
        self.log_only_in_sql(logfile)

    def log_only_in_sql(self, logfile):
        while self._id_sets_only_in_sql:
            ids = self._id_sets_only_in_sql.pop()
            self.diff_count += len(ids)
            for sql_id in ids:
                logfile.write(MISSING_IN_COUCH.format(json.dumps(sql_id)))

    def _iter_couch_docs_for_domains(self, *args, **kw):
        print("WARNING scan for orphaned SQL is not supported with --domains")
        return super()._iter_couch_docs_for_domains(*args, **kw)

    def _get_all_couch_docs_for_model(self, chunk_size):
        first_id = None
        couch_ids = []
        for doc in super()._get_all_couch_docs_for_model(chunk_size):
            yield doc
            couch_ids.append(doc["_id"])
            if len(couch_ids) >= chunk_size:
                self.find_rows_only_in_sql(first_id, couch_ids)
                first_id = couch_ids[-1]
                couch_ids = []
        if couch_ids:
            self.find_rows_only_in_sql(first_id, couch_ids, end=True)

    def find_rows_only_in_sql(self, first_id, couch_ids, end=False):
        if len(couch_ids) > 1:
            assert couch_ids[0] < couch_ids[-1], (couch_ids[0], couch_ids[-1])
        id_name = self.sql_class()._migration_couch_id_name
        bounds = {} if end else {f"{id_name}__lt": couch_ids[-1]}
        if first_id is not None:
            assert first_id < couch_ids[0], (first_id, couch_ids[0])
            bounds[f"{id_name}__gt"] = first_id
        ids_only_in_sql = list(
            self.sql_class().objects
            .filter(~Q(**{f"{id_name}__in": couch_ids}), **bounds)
            .values_list(id_name, flat=True)
        )
        if ids_only_in_sql:
            if isinstance(ids_only_in_sql[0], UUID):
                ids_only_in_sql = [x.hex for x in ids_only_in_sql]
            self._id_sets_only_in_sql.append(ids_only_in_sql)

    def delete_rows_only_in_sql(self, diffs_file, logfile, chunk_size):
        couch = self.couch_db()
        sql_ids = DiffDocs(diffs_file, None, chunk_size, MISSING_IN_COUCH)
        id_name = self.sql_class()._migration_couch_id_name
        ignored_count = deleted_count = 0
        for ids in chunked(sql_ids.iter_doc_ids(), chunk_size, list):
            to_delete = ids
            couch_status = couch.view("_all_docs", keys=ids, reduce=False)
            to_delete = []
            for res in couch_status:
                if "value" in res and res["value"].get("deleted"):
                    to_delete.append(res["id"])
                else:
                    ignored_count += 1
                    print("Unexpected: SQL record not deleted in Couch:", res, file=logfile)
            print("Removed orphaned SQL rows:", to_delete, file=logfile)
            self.sql_class().objects.filter(**{f"{id_name}__in": to_delete}).delete()
            deleted_count += len(to_delete)
        if deleted_count:
            print(f"Removed {deleted_count} orphaned SQL rows")
        if ignored_count:
            print(f"Ignored {ignored_count} orphaned SQL rows (not deleted in Couch)")


MISSING_IN_COUCH = "SQL row {} is missing in Couch\n"
