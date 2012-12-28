from calendar import HTMLCalendar
from calendar import  month_name, monthrange
from datetime import date, timedelta, datetime
from itertools import groupby
import pdb
from django import forms
from django.forms.forms import Form
from dimagi.utils import make_time
from dimagi.utils.decorators.memoized import memoized
from pact.dot_data import filter_obs_for_day, DOTDay
from pact.enums import DAY_SLOTS_BY_IDX, DOT_ADHERENCE_EMPTY, DOT_ADHERENCE_PARTIAL, DOT_ADHERENCE_FULL, DOT_OBSERVATION_DIRECT, DOT_OBSERVATION_PILLBOX, DOT_OBSERVATION_SELF, DOT_ADHERENCE_UNCHECKED, DOT_ART, DOT_NONART
from pact.models import CObservation
import settings




class DOTCalendarReporter(object):

    patient_casedoc=None
    start_date=None
    end_date=None

    def unique_xforms(self):
        obs = self.dot_observation_range()
#        ret = set([x[]])
        ret = set([x['doc_id'] for x in filter(lambda y: y.is_reconciliation == False, obs)])
        return ret


    @memoized
    def dot_observation_range(self):
        """
        get the entire range of observations for our given date range.
        """
        case_id = self.patient_casedoc._id
        observations = query_observations(case_id, self.start_date, self.end_date)
        return observations

    def __init__(self, patient_casedoc, start_date=None, end_date=None):
        """
        patient_casedoc is a CommCareCase document
        """
        self.patient_casedoc = patient_casedoc
        self.start_date = start_date
        if end_date is None:
            self.end_date = make_time()
        else:
            self.end_date=end_date

        if start_date is None:
            self.start_date = end_date - timedelta(days=14)
        else:
            self.start_date=start_date

    @property
    def calendars(self):
        """
        Return calendar(s) spanning OBSERVED dates for the given encounter_date range.
        In reality this could exceed the dates ranged by the encounter dates since the start_date is a 20 day retrospective.

        Return iterator of calendars
        """
        startmonth = self.start_date.month
        startyear = self.start_date.year
        endmonth = self.end_date.month

        currmonth = startmonth
        curryear = startyear
        observations = self.dot_observation_range()

        def endcur_in_obs(currmonth, curryear, observations):
            month_days = monthrange(curryear, currmonth)[1]
            if (curryear, currmonth) <= (observations[-1].observed_date.year, observations[-1].observed_date.month):
                return True
            else:
                return False

        while endcur_in_obs(currmonth, curryear, observations):
        #while currmonth % 13 + 1 <= endmonth:
            cal = DOTCalendar(self.patient_casedoc, observations)
            yield cal.formatmonth(curryear, currmonth)
            currmonth += 1
            if currmonth == 13:
                #roll over, flip year
                curryear+=1
                currmonth = 1


class DOTCalendar(HTMLCalendar):
    #source: http://journal.uggedal.com/creating-a-flexible-monthly-calendar-in-django/
    cssclasses = ["mon span2", "tue span2", "wed span2", "thu span2", "fri span2", "sat span2", "sun span2"]

    observations = []
    patient_casedoc=None

    def __init__(self, patient_casedoc, observations):
        super(DOTCalendar, self).__init__()
        #self.submissions = self.group_by_day(submissions)
        #self.django_patient = django_patient
        self.patient_casedoc = patient_casedoc
        self.observations = observations

    def formatmonthname(self, theyear, themonth, withyear=True):
        """
        Return a month name as a table row.
        """
        #make sure to roll over year?
        nextyear=theyear
        prevyear=theyear
        if themonth + 1 > 12:
            nextmonth=1
            nextyear=theyear+1
        else:
            nextmonth=themonth+1
        if themonth-1 == 0:
            prevmonth = 12
            prevyear=theyear-1
        else:
            prevmonth=themonth-1

        if withyear:
            s = '%s %s' % (month_name[themonth], theyear)
        else:
            s = '%s' % month_name[themonth]
        return '<tr><th colspan="7" class="month">%s</th></tr>' % s



    def formatday(self, day, weekday):
        if day != 0:
            cssclass = self.cssclasses[weekday]
            this_day = date(self.year, self.month, day)
            if date.today() == this_day:
                cssclass += ' today'
            if date.today() < this_day:
                future=True
            else:
                future=False

            day_observations = filter_obs_for_day(this_day, self.observations)
            if len(day_observations) > 0:
                cssclass += ' filled'
                body = ['<div class="calendar-cell">']
                day_data = DOTDay.merge_from_observations(day_observations)
                #day_data = merge_dot_day(day_observations)

                #for drug_type in day_data.keys():
                for dose_data in [day_data.nonart, day_data.art]:
                    body.append('')
                    body.append('<div class="drug-cell">')
                    body.append('<div class="drug-label">%s</div>' % dose_data.drug_class)

                    #drug_total = day_data[drug_type]['total_doses']
                    drug_total = dose_data.total_doses

                    for dose_num, obs_list in dose_data.dose_dict.items():
                    #for dose_num, obs_list in day_data[drug_type]['dose_dict'].items():
                        if len(obs_list) > 0:
                            obs = obs_list[0]
                            if obs.day_slot != '' and obs.day_slot is not None and obs.day_slot != -1:
                                day_slot_string = DAY_SLOTS_BY_IDX.get(int(obs.day_slot), 'Unknown').title()
                                body.append('<div class="time-label">%s</div>' % day_slot_string)
                            else:
                                #do it by seq?
                                body.append('<div class="time-label">Dose %d</div>' % (int(dose_num) + 1))
                            body.append('<div class="time-cell">')
                            body.append('<div class="observation">')
                            if obs.adherence == DOT_ADHERENCE_UNCHECKED:
                                body.append('<span style="font-size:85%;color:#888;font-style:italic;">unchecked</span>')
                            else:
                                if obs.adherence == DOT_ADHERENCE_EMPTY:
#                                    body.append('<span class="label label-success">Empty</span>')
                                    body.append('<img src="%spact/icons/check.jpg">' % settings.STATIC_URL)
                                elif obs.adherence == DOT_ADHERENCE_PARTIAL:
#                                    body.append('<span class="label label-warning">Partial</span>')
                                    body.append('<img src="%spact/icons/exclamation-point.jpg">' % settings.STATIC_URL)
                                elif obs.adherence == DOT_ADHERENCE_FULL:
#                                    body.append('<span class="label label-important">Full</span>')
                                    body.append('<img src="%spact/icons/x-mark.png">' % settings.STATIC_URL)

                                if obs.method == DOT_OBSERVATION_DIRECT:
#                                    body.append('<span class="label label-info">Direct</span>')
                                    body.append('<img src="%spact/icons/plus.png">' % settings.STATIC_URL)
                                elif obs.method == DOT_OBSERVATION_PILLBOX:
#                                    body.append('<span class="label label-inverse">Pillbox</span>')
                                    body.append('<img src="%spact/icons/bucket.png">' % settings.STATIC_URL)
                                elif obs.method == DOT_OBSERVATION_SELF:
#                                    body.append('<span class="label">Self</span>')
                                    body.append('<img src="%spact/icons/minus.png">' % settings.STATIC_URL)
                            body.append('&nbsp;</div>') #close time-cell
#                            body.append('&nbsp;</div>') #close observation
                        else:
                            #empty observations for this dose_num
                            body.append('<div class="time-label">Dose %d</div>' % (int(dose_num) + 1))
                            body.append('<div class="time-cell">')
                            body.append('<div class="observation">')
                            body.append("empty! &nbsp;</div>")
#                            body.append('&nbsp;</div>')

                        body.append('&nbsp;</div>') #close observation
                    body.append('&nbsp;</div>') # close calendar-cell
                return self.day_cell(cssclass, '%d %s' % (day, ''.join(body)))

            if weekday < 5 and not future:
                missing_link = []
                return self.day_cell(cssclass, "%d %s" % (day, ''.join(missing_link)))
            elif weekday < 5 and future:
                return self.day_cell('future', "%d" % day)
            else:
                return self.day_cell(cssclass, day)
        return self.day_cell('noday', '&nbsp;')

    def formatmonth(self, theyear, themonth, withyear=True):
        """
        Main Entry point
        Return a formatted month as a table.
        """
        self.year, self.month = theyear, themonth
        #return super(SubmissionCalendar, self).formatmonth(year, month)
        #rather than do super, do some custom css trickery
        v = []
        a = v.append
        a('<table border="0" cellpadding="0" cellspacing="0" class="table table-bordered">')
        a('\n')
        a(self.formatmonthname(theyear, themonth, withyear=withyear))
        a('\n')
        a(self.formatweekheader())
        a('\n')
        for week in self.monthdays2calendar(theyear, themonth):
            a(self.formatweek(week))
            a('\n')
        a('</table>')
        a('\n')
        return ''.join(v)

    def group_by_day(self, submissions):
        field = lambda submission: datetime.strptime(submission.form['author']['time']['@value'][0:8], '%Y%m%d').day
        return dict(
            [(day, list(items)) for day, items in groupby(submissions, field)]
        )

    def day_cell(self, cssclass, body):
        return '<td class="%s">%s</td>' % (cssclass, body)

