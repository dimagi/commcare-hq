from datetime import datetime, date
from django.core.management import BaseCommand
from django.db.models import Count
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.es.domains import DomainES


class Command(BaseCommand):
    help = """
    Generate a worker activity report for a given month.
    """

    def add_arguments(self, parser):
        parser.add_argument('--months', default=1, type=int, help="Last X months to evaluate")
        parser.add_argument('--limit', default=10, type=int, help="Grab the top X domains by user count")

    def handle(self, months, limit):
        months_activity = self.collect_worker_activity_data(months, limit)
        # total_number_of_workers_by_domain = 
        # report it

    def collect_worker_activity_data(self, months=None, limit=None):
        """Collects user activity data across domains for ConnectID rollout planning."""
        domain_names = DomainES().real_domains().values_list('name', flat=True)
        
        if not months:
            months = 1
        
        if not limit:
            limit = 10

        months_activity = {}
        for month in range(1, months + 1):
            months_activity[f"month_{month}"] = list(self.get_activity_for_timeframe(month, domain_names, limit))

        return months_activity

    def get_activity_for_timeframe(self, months, domain_names, limit):
        """Get user activity data for specific timeframe."""
        now = datetime.utcnow()
        year, month = add_months(now.year, now.month, -months)
        start_date = date(year, month, 1)

        # Get active users since start_date
        return (
            MALTRow.objects.filter(
                month__gte=start_date,
                num_of_forms__gte=1,
                domain_name__in=domain_names,
            )
            .values("user_id", "app_id")  # group by user and app
            .annotate(month_count=Count('month', distinct=True))  # count distinct months this user has a record for this app
            .filter(month_count=months)  # makes sure the user has activity for all months in the range
            .values("domain_name", "app_id")
            .annotate(user_count=Count("user_id", distinct=True))  # count distinct users for each app in the domain
            .order_by("-user_count")[:limit]  # sorted by user count and limited to the top results
        )

def add_months(year, months, offset):
    """
    Add a number of months to the passed in year and month, returning
    a tuple of (year, month)
    """
    months = months - 1  # 0 index months coming in
    nextmonths = months + offset
    months_offset = nextmonths % 12 + 1  # 1 index it going out
    years_offset = nextmonths // 12
    return (year + years_offset, months_offset)
