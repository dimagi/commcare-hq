import time
from datetime import datetime

from corehq.apps.case_search.utils import get_case_search_results_from_request
from corehq.apps.users.models import CouchUser

from gevent.pool import Pool

app_id = "314ffdb259ad4944a4063112ab3d555c",
my_clients_one_clinc = {"_xpath_query":["central_registry = \"yes\" and subcase-exists(\"parent\", @case_type = \"service\" and @status != \"closed\" and central_registry = \"yes\" and selected(clinic_case_id,\"17eb1fcd-c3fa-455c-9d21-110dd01138b1\"))","match-none() or match-none() or match-none() or match-none() or  (\n(\n(\n(\nfuzzy-match(\nfirst_name, \n\"Cal\"\n) or phonetic-match(\nfirst_name, \n\"Cal\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Ellowitz\"\n) or phonetic-match(\nlast_name, \n\"Ellowitz\"\n)\n)\n) or subcase-exists (\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and (\n(\nfuzzy-match(\nfirst_name, \n\"Cal\"\n) or phonetic-match(\nfirst_name, \n\"Cal\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Ellowitz\"\n) or phonetic-match(\nlast_name, \n\"Ellowitz\"\n)\n)\n)\n)\n) and (\nmatch-all()\n)\n) ","current_status = \"admitted\" and selected(active_admission_clinic_id, \"17eb1fcd-c3fa-455c-9d21-110dd01138b1\")","match-all()","match-all()"],"case_type":["client"]}
my_clients_two_clinics = {"_xpath_query":["central_registry = \"yes\" and subcase-exists(\"parent\", @case_type = \"service\" and @status != \"closed\" and central_registry = \"yes\" and selected(clinic_case_id,\"a3c6d21b-7656-4b41-a908-f60838075022 bd32d9f3-8c8a-4749-88c0-ac8ac56b7e4d\"))","match-none() or match-none() or match-none() or match-none() or  (\n(\n(\n(\nfuzzy-match(\nfirst_name, \n\"Graham\"\n) or phonetic-match(\nfirst_name, \n\"Graham\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n) or subcase-exists (\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and (\n(\nfuzzy-match(\nfirst_name, \n\"Graham\"\n) or phonetic-match(\nfirst_name, \n\"Graham\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n)\n)\n) and (\nmatch-all()\n)\n) ","current_status = \"admitted\" and selected(active_admission_clinic_id, \"a3c6d21b-7656-4b41-a908-f60838075022 bd32d9f3-8c8a-4749-88c0-ac8ac56b7e4d\")","match-all()","match-all()"],"case_type":["client"]}
my_clients_three_clinics = {"_xpath_query":["central_registry = \"yes\" and subcase-exists(\"parent\", @case_type = \"service\" and @status != \"closed\" and central_registry = \"yes\" and selected(clinic_case_id,\"9fc5282c-2b2b-4eeb-a4ef-09c8c4fec7c3 162bb681-a621-4a8f-a534-72feca54cdbe ce3cbc37-fd1c-4e44-b970-178260c1b63c\"))","match-none() or match-none() or match-none() or match-none() or  (\n(\n(\n(\nfuzzy-match(\nfirst_name, \n\"Graham\"\n) or phonetic-match(\nfirst_name, \n\"Graham\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n) or subcase-exists (\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and (\n(\nfuzzy-match(\nfirst_name, \n\"Graham\"\n) or phonetic-match(\nfirst_name, \n\"Graham\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n)\n)\n) and (\nmatch-all()\n)\n) ","current_status = \"admitted\" and selected(active_admission_clinic_id, \"9fc5282c-2b2b-4eeb-a4ef-09c8c4fec7c3 162bb681-a621-4a8f-a534-72feca54cdbe ce3cbc37-fd1c-4e44-b970-178260c1b63c\")","match-all()","match-all()"],"case_type":["client"]}
my_clients_requests = [my_clients_one_clinc, my_clients_two_clinics, my_clients_three_clinics]

search_and_admit_request_one = {"_xpath_query": ["central_registry = \"yes\"","consent_collected = \"yes\"","match-none() or match-none() or social_security_number = \"111111111\" or subcase-exists(\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and social_security_number = \"111111111\"\n) or match-none() or  (\n(\n(\n(\nfuzzy-match(\nfirst_name, \n\"Cal\"\n) or phonetic-match(\nfirst_name, \n\"Cal\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n) or subcase-exists (\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and (\n(\nfuzzy-match(\nfirst_name, \n\"Cal\"\n) or phonetic-match(\nfirst_name, \n\"Cal\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Herceg\"\n) or phonetic-match(\nlast_name, \n\"Herceg\"\n)\n)\n)\n)\n) and (\nfuzzy-match(\ndob, \n\"1995-04-26\"\n) or subcase-exists(\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and fuzzy-match(\ndob, \n\"1995-04-26\"\n)\n)\n)\n) ","@case_id != \"4a3c91cc-dd73-4242-b478-3207820bb886\"","not(selected(@case_id, \"\"))"],"case_type":["client"]}
search_and_admit_request_two = {"_xpath_query":["central_registry = \"yes\"","consent_collected = \"yes\"","match-none() or match-none() or social_security_number = \"123456789\" or subcase-exists(\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and social_security_number = \"123456789\"\n) or match-none() or  (\n(\n(\n(\nfuzzy-match(\nfirst_name, \n\"Amit\"\n) or phonetic-match(\nfirst_name, \n\"Amit\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Phulera\"\n) or phonetic-match(\nlast_name, \n\"Phulera\"\n)\n)\n) or subcase-exists (\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and (\n(\nfuzzy-match(\nfirst_name, \n\"Amit\"\n) or phonetic-match(\nfirst_name, \n\"Amit\"\n)\n) and (\nfuzzy-match(\nlast_name, \n\"Phulera\"\n) or phonetic-match(\nlast_name, \n\"Phulera\"\n)\n)\n)\n)\n) and (\nfuzzy-match(\ndob, \n\"2001-06-24\"\n) or subcase-exists(\n\"parent\", \n@case_type = \"alias\" and @status != \"closed\" and fuzzy-match(\ndob, \n\"2001-06-24\"\n)\n)\n)\n) ","current_status != \"pending\""],"case_type":["client"]}
search_and_admit_requests = [search_and_admit_request_one, search_and_admit_request_two]


repeat_request_count = 1000
retry_interval_secs = 60 * 10  # 10 minutes
sleep_between_requests = 10  # 10 seconds
user = CouchUser.get_by_username('gherceg@dimagi.com')

def time_request(app_id, user, request):
    start = time.time()
    get_case_search_results_from_request("co-carecoordination", app_id, user, request)
    end = time.time()
    total = end - start
    return total



class Command(BaseCommand):
    def handle(**options):
        count = 0
        request_pool = Pool(100)
        while True:
            print(f"Round {count + 1}: {datetime.utcnow()}")

            print("My Clients")
            for request in my_clients_requests:
                for i in range(repeat_request_count):
                    if pool.wait_available():
                        pool.spawn(time_request, app_id, user, request)

            print("Search & Admit")
            for request in search_and_admit_requests:
                for i in range(repeat_request_count):
                    if pool.wait_available():
                        pool.spawn(time_request, app_id, user, request)

            time.sleep(retry_interval_secs)
            count += 1
