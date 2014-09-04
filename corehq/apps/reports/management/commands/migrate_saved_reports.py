from django.core.management import BaseCommand
from corehq.apps.reports.models import ReportConfig
from dimagi.utils.couch.database import iter_docs

AFFECTED_REPORTS = ["daily_form_stats", "case_list", "case_activity", "completion_vs_submission", "completion_times",
                    "submissions_by_form", "submit_history"]

def migrate(config, db):
    def get_list(key):
        ret = config["filters"].pop(key, [])
        ret = [ret] if not isinstance(ret, list) else ret
        return filter(None, ret)

    def divvy(list_of_ids):
        users, groups = [], []
        if list_of_ids:
            for a_id in list_of_ids:
                doc = db.get(a_id)
                if doc.get("doc_type") in ["CommCareUser", "WebUser"]:
                    users.append(a_id)
                elif doc.get("doc_type") == "Group":
                    groups.append(a_id)
        return users, groups

    if config.get("report_slug") in AFFECTED_REPORTS:
        ufilters = get_list("ufilter")
        groups = get_list("group")
        users = get_list("select_mw")
        indy_users, indy_groups = divvy(get_list("individual"))
        users += indy_users
        groups += indy_groups
        users = ["u__%s" % u_id for u_id in users]
        groups = ["g__%s" % g_id for g_id in groups]
        ufilters = ["t__%s" % t_id for t_id in ufilters]
        config["filters"]["emw"] = config["filters"].get("emw", []) +  users + groups + ufilters
        if config["filters"].get("emw"):
            return True

    return False

class Command(BaseCommand):
    args = ""
    help = """
        Loops through every ReportConfig and changes the group and user filters
        to the format used by CombinedSelectUsers filter
    """

    def handle(self, *args, **options):
        db = ReportConfig.get_db()
        results = db.view('reportconfig/configs_by_domain',
            startkey=["name"], endkey=["name", {}],
            reduce=False,
            include_docs=False,
        ).all()

        configs_to_save = []
        for config in iter_docs(db, [r['id'] for r in results]):
            if migrate(config, db):
                configs_to_save.append(config)

            if len(configs_to_save) > 100:
                db.bulk_save(configs_to_save)
                configs_to_save = []
        db.bulk_save(configs_to_save)