from django.conf import settings
from django.db import connection


class QueryCountDebugMiddleware:
    enabled = True
    show_details = False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Reset counter on each request
        connection.queries_log.clear()
        response = self.get_response(request)
        if settings.DEBUG and self.enabled:
            relevant_queries = [
                query for query in connection.queries
                if 'data_cleaning' in query['sql']
            ]
            total_time = sum(float(query['time']) for query in relevant_queries)
            count = len(relevant_queries)
            print(f"\n\n\t\t[DB - {total_time}] {request.path} → {count} SQL queries")
            if self.show_details:
                for query in relevant_queries:
                    # Only log queries related to data cleaning
                    time_details = query['time']
                    if len(query['sql']) < 1000:
                        print(f"\t\t\t\t[DB - {time_details}s] {query['sql']}")
                    else:
                        print(f"\t\t\t\t[DB - {time_details}s] {query['sql'][:1000]}... (truncated)")
        return response
