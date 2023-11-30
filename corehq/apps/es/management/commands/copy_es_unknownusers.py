from django.core.management import BaseCommand

from corehq.apps.es.client import get_client


class Command(BaseCommand):

    help = ("A one-off command to copy UnknownUser/AdminUser docs from hqusers_2017-09-07 "
            "to users-20231128. This copies the domain_membership field to domain_memberships "
            "field using the painless script.")

    def handle(self, *args, **options):
        reindex_body = {
            "source": {
                "index": "hqusers_2017-09-07",
                "size": 1000,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "exists": {
                                    "field": "domain_membership"
                                }
                            },
                            {
                                "terms": {
                                    "doc_type": [
                                        "UnknownUser",
                                        "AdminUser"
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
            "dest": {
                "index": "users-20231128",
                "op_type": "create",
                "version_type": "external"
            },
            "conflicts": "proceed",
            "script": {
                "source": "if (ctx._source.containsKey('domain_membership')) {if (ctx._source.doc_type == 'UnknownUser' || ctx._source.doc_type == 'AdminUser') {ctx._source.domain_memberships = ctx._source.domain_membership;}}"
            }
        }
        es = get_client()
        reindex_info = es.reindex(
            reindex_body,
            wait_for_completion=False,
            refresh=True,
        )
        task_id = reindex_info['task']
        print("\n\n\n")
        print(f"TASK ID - {task_id}")
        print("-------------------------------------------")
        print("Save this Task ID, you can use this to check status of the reindex progress")
        print("Using https://www.elastic.co/guide/en/elasticsearch/reference/5.6/tasks.html")
        print("\n\n\n")
