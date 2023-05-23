import argparse
import re
from textwrap import dedent

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = dedent("""\
    Verify if a reindex process is completed in a ElasticSearch 2 cluster. The command parses the logs for reindex and provides detailed information of the process.

    The log should be extracted from elasticsearch logs. It can be done using commcare cloud.
    
    ```
    cchq <env> run-shell-command elasticsearch "cat /opt/data/elasticsearch*/logs/*es.log | grep <task_id>"
    ```

    If the above command fail to yeild any output then the reindex log should be manually searched in elasticsearch logs.

    So running this command should look something like

    ./manage.py verify_reindex --eslog '[2023-05-23 08:59:37,648][INFO] [tasks] 29216 finished with response ReindexResponse[took=1.8s,updated=0,created=1111,batches=2,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[],search_failures=[]]'
    """)

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument("-l", "--eslog", required=True, help="Reindex log string from es logs")

    def handle(self, eslog, **options):
        self._assert_valid_log_string(eslog)

        response = self._parse_reindex_response(eslog)
        if response['indexing_failures']:
            print(f"Reindex Failed because of Indexing Failures - {response['indexing_failures']}")
        elif response['search_failures']:
            print(f"Reindex Failed because of Search Failures" - {response['search_failures']})
        elif response.get('canceled'):
            print(f"Reindex cancelled becuase - {response['canceled']}")
        else:
            print("Reindex Successful -")


    def _assert_valid_log_string(self, log_string):
        invalid_string = False
        task_id = self._parse_task_id(log_string)
        try:
            int(task_id)
        except ValueError:
            invalid_string = True
        if not "ReindexResponse[" in log_string:
            invalid_string= True
        if invalid_string:
            raise ValueError("""Invalid log string provided. The log string should be of format - \
                '[2023-05-23 08:59:37,648][INFO] [tasks] 29216 finished with response ReindexResponse[took=1.8s,updated=0,created=1111,batches=2,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[],search_failures=[]]'
            """)
        
    def _parse_task_id(self, log_string):
        task_id_start = log_string.find("tasks] ") + len("tasks] ")
        task_id_end = log_string.find(" finished")
        task_id = log_string[task_id_start:task_id_end]
        return task_id

    def _parse_reindex_response(self, log_string):
        response_start = log_string.find("ReindexResponse[") + len("ReindexResponse[")
        response_end = log_string.rfind("]")
        response_data = log_string[response_start:response_end]
        # Parsing response details
        response_dict = {}
        if response_data:
            # Find all tokens of format a=b, or a=[b,c],
            items =  re.findall(r'(\w+)=(\[.*?\]|[^,\]]+)', response_data)
            
            for tokens in items:
                key = tokens[0].strip()
                value_str = tokens[1].strip()
                # Process array fields
                if value_str.startswith('[') and value_str.endswith(']'):
                    value_str = value_str[1:-1]
                    value_arr = value_str.split(',') if value_str else []
                    value = [val.strip() for val in value_arr]
                else:
                    value = value_str
                response_dict[key] = value
        return response_dict


