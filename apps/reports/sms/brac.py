""" 
rO - oct 25 2009 - sticking in 'sms' temporarily. feel free to move somewhere else.
(then update reports/tests/brac.py import statement accordingly)

BRAC SMS Reports

Notes:
Report-generic information is stored in 'contexts'
SMS reports are only sent to users where reporter_profile.active=True

Possible Future Extension?
* some sort of subscription model, so that users could 'opt out' on a per-alert basis
"""

import logging
from rapidsms.i18n import ugettext_from_locale as _t
from rapidsms.i18n import ugettext_noop as _
from reporters.models import Reporter

from domain.models import Domain
from hq.models import Organization, ReporterProfile
from hq.reporter.custom import get_delinquent_context_from_statdict
from reports.sms.util import forms_submitted
import hq.reporter.metastats as metastats

def brac_sms_report(router, reporter_map = {}):
    
    """Send to manually-coded numbers, set via the args in the 
       scheduler app.  If nothing is set, nothign will be sent.
    """
    for chw_name, reporter_name in reporter_map.items():
        count = forms_submitted(chw_name, weeks=1)
        rep = Reporter.objects.get(alias__iexact=reporter_name)
        send_activity_to_reporter(router, rep, chw_name, count)
    

def weekly(router):
    # todo - move 'brac' to db (eventschedule.callback_args)
    brac = Domain.objects.get(name="BRAC")
    activity_report(router, brac)

def daily(router):
    # todo - move 'brac' to db (eventschedule.callback_args)
    brac = Domain.objects.get(name="BRAC")
    delinquent_report(router, brac)
    
def activity_report(router, domain, send_chv_report=True, 
                    send_super_report=True, send_summary_chv_report=True):
    """
       Sends weekly activity reports to CHV's and CHW's
       Later: we can always break this out into its own schedule at a later date
    """
    logging.info("Running brac sms activity report")
    orgs = Organization.objects.filter(domain=domain)
    for org in orgs:
        members = org.get_members().filter(active=True)
        for member in members:
            form_count = forms_submitted(member.chw_username, weeks=1)
            if send_chv_report:
                # tell individual chv's of their usage this past week
                send_activity_to_reporter(router, member, member.chw_username, form_count)
            if send_super_report:
                supervisors = org.get_supervisors().filter(active=True)
                for supe in supervisors:
                    # each supervisor gets one activity report for each chv supervised
                    send_activity_to_super(router, supe, {'chv':member, 'count': form_count} )
            member.forms_this_week = form_count
        if send_summary_chv_report:
            for member in members:
                # each chv receives a summary of activity within their branch
                send_summary_activity_to_reporter(router, member, {'group_members':members} )

def send_activity_to_reporter(router, recipient, username, forms_submitted ):
    """ SMS document 1: first set 
        Messages chv with a report of her activity in the past week
    """
    logging.debug("Running brac sms send_activity_to_reporter")
    if forms_submitted >= 45:
        greeting = _t( _("Congratulations for the work done %(username)s. "), 
                       recipient.language)
        instructions = ""
    elif forms_submitted >= 26:
        greeting = _t( _("Thank you %(username)s. "), recipient.language)
        instructions = _t( _("Please do your best to complete and send all the forms. "), 
                             recipient.language)
    else:
        greeting = _t( _("Sorry for the trouble %(username)s. "), recipient.language)
        instructions = _t( _("Please remember to fill and send the complete reports every week. "), 
                             recipient.language)
    info = _t(_("You have submitted %(count)s forms this week. "), recipient.language)
    response = greeting + info + instructions + \
               _t(_("If the number is incorrect, call Gayo 0786151272."), recipient.language)
    response = response % { 'username':username, 'count':forms_submitted }
    recipient.send_message(router, response)
    
def send_activity_to_super(router, recipient, context ):
    """ SMS document 1: second set 
        Messages supervisor with activity report for a given chv
    """
    logging.debug("Running brac sms send_activity_to_super")
    forms_submitted = context['count']
    chv = context['chv']
    if forms_submitted >= 45:
        response = _t( _("%(username)s has submitted %(count)s forms this week. "), recipient.language) + \
          _t( _("A work well done!"), recipient.language)
    elif forms_submitted >= 26:
        response = _t( _("%(username)s has submitted %(count)s forms this week. "), recipient.language) + \
          _t( _("Please remind her to submit all the forms every week"), recipient.language)
    else:
        response = _t( _("%(username)s has submitted %(count)s forms this week. "), recipient.language) + \
          _t( _("Please do follow up and ask what seems to be the problem."), recipient.language)
    response = response % { 'username':chv.chw_username, 'count':forms_submitted }
    recipient.send_message(router, response)

def send_summary_activity_to_reporter(router, recipient, context ):
    """ SMS document 1: third set 
    Messages all chv's with a summary of activity from their group
    """
    logging.debug("Running brac sms send_summary_activity_to_reporter")
    response = []
    for chv in context['group_members']:
        response.append( _t( _("%(username)s submitted %(count)s forms"), 
                             recipient.language ) % 
                             { 'username':chv.chw_username, 'count':chv.forms_this_week } )
    response = _t(_("Forms submitted: "), recipient.language) + ", ".join(response)
    recipient.send_message(router, response)

def delinquent_report(router, domain, send_delinquent_chv=True, send_summary=True):
    logging.info("Running brac sms delinquent report")
    organizations = Organization.objects.filter(domain=domain)
    for org in organizations:
        threshold = 2 # delinquent if we have not seen them in 2 days
        delinquents = []
        statdict = metastats.get_stats_for_organization(org, match_by_username=True)
        context = get_delinquent_context_from_statdict(statdict, threshold)
        if send_delinquent_chv:
            for chv in context['delinquent_reporterprofiles']:
                last_seen = statdict[chv]['Time since last submission (days)']
                # message all delinquent users
                alert_delinquent_reporter(router, chv, {'last_seen':last_seen} )
        if send_summary:
            supervisors = org.get_supervisors().filter(active=True)
            for supe in supervisors:
                # send summary to supervisors
                send_summary_delinquent_to_super(router, supe, context)

def alert_delinquent_reporter(router, recipient, context):
    """ SMS document 2: first set
    Send chv an alert when they haven't submitted anything in 2 days
    """
    logging.debug("Running brac sms alert_delinquent_reporter")
    last_seen = context['last_seen']
    # do not break this string without updating the translation files
    response = _t( _("Hi %(username)s, we haven't received any forms " +
                     "from you for the last %(count)s days. " + 
                     "Please send your forms."), 
                 recipient.language) % \
                 { 'username':recipient.chw_username, 'count':last_seen }
    recipient.send_message(router, response)

def send_summary_delinquent_to_super(router, recipient, context):
    """ SMS document 2: second set 
    Send all supervisors a summary of delinquent chv's
    """
    logging.debug("Running brac sms send_summary_delinquent_to_super")
    usernames = [chv.chw_username for chv in context['delinquent_reporterprofiles']]
    if usernames is None or len(usernames)==0:
        recipient.send_message(router, _t(_('No delinquents found for delinquent alert'),recipient.language))
    response = ", ".join(usernames)
    response = response + _t( _(" has not sent any forms for 2 or more days. " + \
               "Please follow up to determine the problem."), recipient.language)
    recipient.send_message(router, response)
    
