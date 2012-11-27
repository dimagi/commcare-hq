from datetime import datetime
from django.http import Http404
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from pact.models import CDotWeeklySchedule, PactPatientCase
from pact.reports import PactPatientDispatcher, PactPatientReportMixin, PatientNavigationReport



class PactPatientInfoReport(PactPatientReportMixin, CustomProjectReport):
#    name = "Patient Info"
    slug = "patient"
    description = "some patient"

#    asynchronous=False


    def prepare_schedule(self, patient_doc, context):
        #patient_doc is the case doc
        computed = patient_doc['computed_']

        def get_current(x):
            if x.deprecated:
                return False
            if x.ended is None and x.started < datetime.utcnow():
                return True
            if x.ended < datetime.utcnow():
                return False

            print "made it to the end somehow..."
            print '\n'.join(x.weekly_arr)
            return False

        if computed.has_key('pact_weekly_schedule'):
            schedule_arr = [CDotWeeklySchedule.wrap(x) for x in computed['pact_weekly_schedule']]

            past = filter(lambda x: x.ended is not None and x.ended < datetime.utcnow(), schedule_arr)
            current = filter(get_current, schedule_arr)
            future = filter(lambda x: x.deprecated and x.started > datetime.utcnow(), schedule_arr)

#            print '\n'.join([x.weekly_arr() for x in current])
            past.reverse()
            print current
            if len(current) > 1:
                for x in current:
                    print '\n'.join(x.weekly_arr())

            context['current_schedule'] = current[0]
            context['past_schedules'] = past
            context['future_schedules'] = future


    @memoized
    def get_case(self):
        self._case_doc = PactPatientCase.get(self.request.GET['patient_id'])
        return self._case_doc

    @property
    def name(self):
        if hasattr(self, 'request'):
            if self.request.GET.get('patient_id', None) is not None:
                case = self.get_case()
                return "Patient Info :: %s" % case.name
        else:
            return "Patient Info"

    @property
    def report_context(self):
        patient_doc = self.get_case()
        view_mode = self.request.GET.get('view', 'info')
        ret = {'patient_doc': patient_doc}
        ret['pt_root_url'] = PactPatientInfoReport.get_url(*[self.request.domain]) + "?patient_id=%s" % self.request.GET['patient_id']
        ret['view_mode'] = view_mode
        print ret

        if view_mode == 'info':
            self.report_template_path = "pact/patient/pactpatient_info.html"
        elif view_mode == 'submissions':
            self.report_template_path = "pact/patient/pactpatient_submissions.html"
        elif view_mode == 'schedule':
            self.prepare_schedule(patient_doc, ret)
            self.report_template_path = "pact/patient/pactpatient_schedule.html"
        else:
            raise Http404
        return ret


    @classmethod
    def get_foo(cls, *args, **kwargs):
        print "get url"
        patient_case_id = kwargs.get('pt_case_id')
        url = super(PactPatientInfoReport, cls).get_url(*args, **kwargs)
        print url
        print patient_case_id
        return "%s%s" % (url, "%s/" % patient_case_id if patient_case_id else "")
