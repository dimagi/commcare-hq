from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport,\
    SummaryTablularReport
import random
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from datetime import datetime, timedelta

class ConvenientBaseMixIn(object):
    # for the lazy
    _headers = []  # override
    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(h) for h in self._headers))

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as
            
    
class MockTablularReport(ConvenientBaseMixIn, GenericTabularReport, CustomProjectReport):
    hide_filters = True
    flush_layout = True
    mobile_enabled = True
    
    row_count = 20 # override if needed
    def _row(self, i):
        # override
        raise NotImplementedError("Override this!")
    
    @property
    def report_context(self):
        return super(MockTablularReport, self).report_context
    
    @property
    def rows(self):
        return [self._row(i) for i in range(self.row_count)]

class MockSummaryReport(ConvenientBaseMixIn, SummaryTablularReport, CustomProjectReport):
    hide_filters = True
    flush_layout = True
    mobile_enabled = True
    
    def fake_done_due(self, i=20):
        # highly customized for gates
        return "(%(done)s Done / %(due)s Due)" % \
            {"done": random.randint(0, i),
             "due": i}
            
class MockNavReport(MockSummaryReport):
    # this is a bit of a bastardization of the summary report
    # but it is quite DRY
    @property
    def reports(self):
        # override
        raise NotImplementedError("Override this!")
    
    @property
    def _headers(self):
        return [" "] * len(self.reports)
    
    @property
    def data(self):
        def _nav_link(report_cls):
            return '<a href="%(details)s?facility=%(val)s">%(val)s</a>' % \
                {"val": report_cls.name, 
                 "details": report_cls.get_url(self.domain, 
                                               render_as=self.render_next)}
        return [_nav_link(report_cls) for report_cls in self.reports]
        

        
class SubCenterSelectionReport(MockTablularReport):
    name = "Select Subcenter"
    slug = "subcenter"
    description = "Subcenter selection report"
    
    _headers = ["AWCC", "Team Name", "Rank"]
    def _row(self, i):
        
        def _link(val):
            return '<a href="%(details)s?facility=%(val)s">%(val)s</a>' % \
                {"val": val,
                 "details": TeamDetailsReport.get_url(self.domain, 
                                                      render_as=self.render_next)}
        return ["009", _link("Khajuri Team %s" % i), 
                "%s / %s" % (random.randint(0, i), i)] \
                
        
class TeamDetailsReport(MockSummaryReport):
    name = "Team Details"
    slug = "teamdetails"
    description = "Team details report"
    
    _headers = ["Team Name", 
                "BP (2nd Tri) Visits Due and Visits Done in last 30 days", 
                "BP (3rd Tri) Visits Due and Visits Done in last 30 days", 
                "Deliveries Visited in 24 hours of Birth at Home Due and Done in last 30 days", 
                "Deliveries Visited in 24 hours of Birth at Institution Due and Done in last 30 days", 
                "PNC Visits Due and Visits Done in last 30 days", 
                "EBF Visits Due and Visits Done in last 30 days", 
                "CF Visits Due and Visits Done in last 30 days"] 

    @property
    def data(self):
        def _link(val):
            return '<a href="%(details)s?facility=%(val)s">%(val)s</a>' % \
                {"val": val, 
                 "details": TeamNavReport.get_url(self.domain, 
                                                  render_as=self.render_next)}
        
        return [_link("Khajuri Team 1")] + \
                [self.fake_done_due(i) for i in range(len(self._headers) - 1)]

class TeamNavReport(MockNavReport):
    name = "Team Navigation List"
    slug = "teamnav"
    description = "Team navigation"
    
    @property
    def reports(self):
        return [PregnanciesRegistered, NoBPCounseling, RecentDeliveries]
    
class MotherListReport(MockTablularReport):
    name = "Mother List"
    slug = "motherlist"
    description = "Mother details report"
    
    _headers = ["Name", "EDD"] 
    
    def _row(self, i):
        def _random_edd():
            return (datetime.now() + timedelta(days=random.randint(0, 9 * 28))).strftime("%Y-%m-%d" )
        return ["Mother %s" % i, _random_edd()]
        
class PregnanciesRegistered(MotherListReport):
    name = "Pregnancies Registered"
    slug = "pregreg"
    
class NoBPCounseling(MotherListReport):
    name = "Mothers Not Given BP Counseling"
    slug = "nobp"
    
class RecentDeliveries(MotherListReport):
    name = "Recent Deliveries"
    slug = "recentdeliveries"
    
    