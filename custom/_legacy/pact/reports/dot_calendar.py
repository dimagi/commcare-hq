from calendar import HTMLCalendar
from calendar import month_name
from datetime import date, timedelta, datetime
from itertools import groupby
import logging
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from dimagi.utils.decorators.memoized import memoized
from pact.dot_data import (
    DOTDay,
    filter_obs_for_day,
    query_observations,
    query_observations_singledoc,
)
from pact.enums import (
    DAY_SLOTS_BY_IDX,
    DOT_ADHERENCE_EMPTY,
    DOT_ADHERENCE_FULL,
    DOT_ADHERENCE_PARTIAL,
    DOT_ADHERENCE_UNCHECKED,
    DOT_OBSERVATION_DIRECT,
    DOT_OBSERVATION_PILLBOX,
    DOT_OBSERVATION_SELF,
)
from pytz import timezone
from django.conf import settings


def make_time():
    return datetime.now(tz=timezone(settings.TIME_ZONE))


class DOTCalendarReporter(object):

    patient_casedoc = None
    start_date = None
    end_date = None

    observe_start_date = None
    observe_end_date = None

    def unique_xforms(self):
        obs = self.dot_observation_range()
        ret = set([x['doc_id'] for x in filter(lambda y: y.is_reconciliation is False, obs)])
        return ret

    @memoized
    def dot_observation_range(self):
        """
        get the entire range of observations for our given date range.
        """
        if self.single_submit is None:
            case_id = self.patient_casedoc._id
            observations = query_observations(case_id, self.start_date, self.end_date)
        else:
            observations = query_observations_singledoc(self.single_submit)

        return sorted(observations, key=lambda x: x['observed_date'])

    def __init__(self, patient_casedoc, start_date=None, end_date=None, submit_id=None):
        """
        patient_casedoc is a CommCareCase document

        if submit_id, just do that ONE submit
        """
        self.patient_casedoc = patient_casedoc
        self.start_date = start_date
        self.single_submit = submit_id
        if end_date is None:
            # Danny March 24, 2015
            logging.error("I don't think this ever happens, but rather than "
                          "trying to figure that out right now, I'll just "
                          "leave this here. If you get Sentry errors or "
                          "see this in the logs, I apologize, and go ahead "
                          "and delete this logging. If you come across this "
                          "and it's been a number of month, feel free to "
                          "delete this code path as well as the "
                          "absurd make_time function.")
            self.end_date = make_time()
        else:
            self.end_date=end_date

        if start_date is None:
            self.start_date = end_date - timedelta(days=14)
        else:
            self.start_date = start_date

    @property
    def calendars(self):
        """
        Return calendar(s) spanning OBSERVED dates for the given encounter_date range.
        In reality this could exceed the dates ranged by the encounter dates since the start_date is a 20 day retrospective.

        Return iterator of calendars
        """
        # startmonth = self.start_date.month
        # startyear = self.start_date.year
        # endmonth = self.end_date.month

        observations = self.dot_observation_range()
        if len(observations) > 0:
            startmonth = observations[0].observed_date.month
            startyear = observations[0].observed_date.year

            endmonth = observations[-1].observed_date.month
            endyear = observations[0].observed_date.year
        else:
            startmonth = datetime.now().month
            startyear = datetime.now().year

        currmonth = startmonth
        curryear = startyear

        def endcur_in_obs(currmonth, curryear, observations):
            if len(observations) == 0:
                return False
            if (curryear, currmonth) <= (endyear, endmonth):
                return True
            else:
                return False

        while endcur_in_obs(currmonth, curryear, observations):
            cal = DOTCalendar(self.patient_casedoc, observations)
            yield cal.formatmonth(curryear, currmonth)
            currmonth += 1
            if currmonth == 13:
                # roll over, flip year
                curryear += 1
                currmonth = 1


class DOTCalendar(HTMLCalendar):
    # source: http://journal.uggedal.com/creating-a-flexible-monthly-calendar-in-django/
    cssclasses = ["mon span2", "tue span2", "wed span2", "thu span2", "fri span2", "sat span2", "sun span2"]

    observations = []
    patient_casedoc = None

    def __init__(self, patient_casedoc, observations):
        super(DOTCalendar, self).__init__()
        self.patient_casedoc = patient_casedoc
        self.observations = observations

    def formatmonthname(self, theyear, themonth, withyear=True):
        """
        Return a month name as a table row.
        """

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
            future = (date.today() < this_day)

            day_observations = filter_obs_for_day(this_day, self.observations)
            if len(day_observations) > 0:
                cssclass += ' filled'
                body = ['<div class="calendar-cell">']
                day_data = DOTDay.merge_from_observations(day_observations)

                day_notes = set()
                for dose_data in [day_data.nonart, day_data.art]:
                    body.append('')
                    body.append('<div class="drug-cell">')
                    body.append('<div class="drug-label">%s</div>' % dose_data.drug_class)

                    for dose_num, obs_list in dose_data.dose_dict.items():
                        if len(obs_list) > 0:
                            obs = obs_list[0]

                            if obs.day_note is not None and len(obs.day_note) > 0:
                                day_notes.add(obs.day_note)

                            if obs.day_slot != '' and obs.day_slot is not None and obs.day_slot != -1:
                                day_slot_string = DAY_SLOTS_BY_IDX.get(int(obs.day_slot), 'Unknown').title()
                                body.append('<div class="time-label">%s</div>' % day_slot_string)
                            else:
                                # do it by seq?
                                body.append('<div class="time-label">Dose %d</div>' % (int(dose_num) + 1))
                            body.append('<div class="time-cell">')
                            body.append('<div class="observation">')
                            if obs.adherence == DOT_ADHERENCE_UNCHECKED:
                                body.append('<span style="font-size:85%;color:#888;font-style:italic;">unchecked</span>')
                            else:
                                if obs.adherence == DOT_ADHERENCE_EMPTY:
                                    body.append('<img src="%s">' % static('pact/icons/check.jpg'))
                                elif obs.adherence == DOT_ADHERENCE_PARTIAL:
                                    body.append('<img src="%s">' % static('pact/icons/exclamation-point.jpg'))
                                elif obs.adherence == DOT_ADHERENCE_FULL:
                                    body.append('<img src="%s">' % static('pact/icons/x-mark.png'))

                                if obs.method == DOT_OBSERVATION_DIRECT:
                                    body.append('<img src="%s">' % static('pact/icons/plus.png'))
                                elif obs.method == DOT_OBSERVATION_PILLBOX:
                                    body.append('<img src="%s">' % static('pact/icons/bucket.png'))
                                elif obs.method == DOT_OBSERVATION_SELF:
                                    body.append('<img src="%s">' % static('pact/icons/minus.png'))
                            # close time-cell
                            body.append('&nbsp;</div> <!-- close time-cell -->')
                        else:
                            # empty observations for this dose_num
                            body.append('<div class="time-label">Dose %d</div>' % (int(dose_num) + 1))
                            body.append('<div class="time-cell">')
                            body.append('<div class="observation">')
                            body.append("empty! &nbsp;</div>")

                        # close observation
                        body.append('&nbsp;</div> <!-- close observation -->')

                    # close calendar-cell
                    body.append('&nbsp;</div> <!-- close calendar cell -->')
                if len(day_notes) > 0:
                    body.append('<div class="date-notes-block">')
                    body.append('<i class="icon-info-sign"></i>&nbsp;')
                    body.append('<small>%s</small>' % ('<br>'.join(day_notes)))
                    body.append('</div> <!-- end notes -->')
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
        # rather than call super, do some custom css trickery
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
        def field(submission):
            datetime_string = submission.form['author']['time']['@value'][0:8]
            return datetime.strptime(datetime_string, '%Y%m%d').day
        return {day: list(items) for day, items in groupby(submissions, field)}

    def day_cell(self, cssclass, body):
        return '<td class="%s">%s</td>' % (cssclass, body)
