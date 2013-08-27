# clarify: "No. of women registered under BCSP" refers only to OPEN cases?
# Number of Service Availability Forms Filled Out in Time Period --> VHND Services

from .constants import *
from .models import OpmUserFluff

class Worker(object):
    method_map = [
        ('name', "List of AWWs"),
        ('awc_name', "AWC Name"),
        ('bank_name', "AWW Bank Name"),
        ('account_number', "AWW Bank Account Number"),
        ('block', "Block Name"),
        ('women_registered', "No. of women registered under BCSP"),
        ('children_registered', "No. of children registered under BCSP"),
        ('service_forms_count', "Submission of Service Availability form"),
        ('growth_monitoring_count', "No. of Growth monitoring Sections Filled for eligible children"),
        ('service_forms_cash', "Payment for Service Availability Form (in Rs.)"),
        ('growth_monitoring_cash', "Payment for Growth Monitoring Forms (in Rs.)"),
        ('month_total', "Total Payment Made for the month (in Rs.)"),
        ('last_month_total', "Amount of AWW incentive paid last month"),
    ]

    def __init__(self, worker):
        self.fluff_doc = OpmUserFluff.get("%s-%s" %
            (OpmUserFluff._doc_type, worker._id))
        self.name = self.fluff_doc.name
        self.awc_name = self.fluff_doc.awc_name
        self.bank_name = self.fluff_doc.bank_name
        self.account_number = self.fluff_doc.account_number
        self.block = self.fluff_doc.block
        self.women_registered = "No. of women registered under BCSP"
        self.children_registered = "No. of children registered under BCSP"
        self.service_forms_count = "Submission of Service Availability form"
        self.growth_monitoring_count = "No. of Growth monitoring Sections Filled for eligible children"
        self.service_forms_cash = "Payment for Service Availability Form (in Rs.)"
        self.growth_monitoring_cash = "Payment for Growth Monitoring Forms (in Rs.)"
        self.month_total = "Total Payment Made for the month (in Rs.)"
        self.last_month_total = "Amount of AWW incentive paid last month"

    # def __init__(self, worker):
    #     self.worker = worker
    #     # change to worker.name
    #     self.name = worker.username_in_report

    #     # to be implemented
    #     self.awc_name = "AWC Name"
    #     self.bank_name = "AWW Bank Name"
    #     self.account_number = "AWW Bank Account Number"
    #     self.block = "Block Name"

    #     self.cases = worker.get_cases().all()
    #     self.forms = worker.get_forms().all()

    # @property
    # def women_registered(self):
    #     # total open cases
    #     # open at END of month
    #     return sum([1 for case in self.cases if not case.closed])
    
    # @property
    # def children_registered(self):
    #     total = 0
    #     for form in self.forms:
    #         if form.xmlns == DELIVERY_XMLNS:
    #             kids = form.form.get('live_birth_amount')
    #             if kids:
    #                 total += int(kids)
    #     return total

    # @property
    # def service_forms_count(self):
    #     return sum([1 for form in self.forms if form.xmlns == VHND_XMLNS])
    
    # @property
    # def growth_monitoring_count(self):
    #     total = 0
    #     for form in self.forms:
    #         if form.xmlns == CHILD_FOLLOWUP_XMLNS:
    #             for child_num in ['1', '2', '3']:
    #                 try:
    #                     total += int(form.form.get('child_%s' % child_num
    #                         ).get('child%s_child_growthmon' % child_num))
    #                 except:
    #                     pass
    #     return total
    
    # @property
    # def service_forms_cash(self):
    #     cash_fixture = 100
    #     return self.service_forms_count * cash_fixture
    
    # @property
    # def growth_monitoring_cash(self):
    #     cash_fixture = 150
    #     return self.growth_monitoring_count * cash_fixture
    
    # @property
    # def month_total(self):
    #     return self.service_forms_cash + self.growth_monitoring_cash
    
    # @property
    # def last_month_total(self):
    #     return "Amount of AWW incentive paid last month"