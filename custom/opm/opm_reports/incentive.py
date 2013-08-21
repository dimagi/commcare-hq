# clarify: "No. of women registered under BCSP" refers only to OPEN cases?
# Number of Service Availability Forms Filled Out in Time Period --> VHND Services

# iterate over forms directly (not cases > forms) to avoid duplicates!

class Worker(object):
    def __init__(self, worker):
        # change to worker.name
        self.name = worker.username_in_report

        # to be implemented
        self.awc_name = "AWC Name"
        self.bank_name = "AWW Bank Name"
        self.account_number = "AWW Bank Account Number"
        self.block = "Block Name"

        self.cases = worker.get_cases().all()
        self.forms = worker.get_forms().all()

    @property
    def women_registered(self):
        # total open cases
        return sum([1 for case in self.cases if not case.closed])
    
    @property
    def children_registered(self):
        total = 0
        for form in self.forms:
            if form.name == "Delivery Form":
                kids = form.form.get('live_birth_amount')
                if kids:
                    total += int(kids)
        return total

    @property
    def service_forms_count(self):
        return sum([1 for form in self.forms if form.name == "VHND Services"])
    
    @property
    def growth_monitoring_count(self):
        total = 0
        for form in self.forms:
            if form.name == "Child Followup":
                for child_num in ['1', '2', '3']:
                    try:
                        total += int(form.form.get('child_%s' % child_num
                            ).get('child%s_child_growthmon' % child_num))
                    except:
                        pass
        return total
    
    @property
    def service_forms_cash(self):
        cash_fixture = 100
        return self.service_forms_count * cash_fixture
    
    @property
    def growth_monitoring_cash(self):
        cash_fixture = 150
        return self.growth_monitoring_count * cash_fixture
    
    @property
    def month_total(self):
        return self.service_forms_cash + self.growth_monitoring_cash
    
    @property
    def last_month_total(self):
        return "Amount of AWW incentive paid last month"