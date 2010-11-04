
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db

def report_list(request, domain):
    template = "reports/report_list.html"
    return render_to_response(request, template, {'domain': domain})

##def clinic_summary(request, group_level=2):
##    report = get_clinic_summary(group_level)
##    return render_to_response(request, "reports/couch_report.html",
##                              {"show_dates": False, "report": report})
#
def user_summary(request, domain):
    results = get_db().view("reports/user_summary", group=True, group_level=2, startkey=[domain], endkey=[domain, {}]).all()
    print results
    report_name = "User Summary Report (number of forms filled in by person)"
    for row in results:
        # this is potentially 3N queries where N is the number of users.
        # could be slimmed down if it starts to be slow
        user_id = row["key"][1]
        try:
            user = get_db().get(user_id)
        except Exception:
            user = None
        row["user"] = user
        # have to swap the start and end keys when you specify descending=true
        row["last_submission_date"] = string_to_datetime(get_db().view("reports/user_summary",
                                                                       group=True, group_level=3,
                                                                       endkey=[domain, user_id],
                                                                       startkey=[domain, user_id, {}],
                                                                       limit=1, descending=True).one()["key"][2])

    return render_to_response(request, "reports/user_summary.html", {
        "domain": domain,
        "show_dates": False,
        "results": results,
        "report": {"name": report_name},
    })
#
##@require_GET
##def entrytime(request):
##    clinic_id = request.GET.get("clinic", None)
##    user_id = request.GET.get("user", None)
##    user_data = {}
##    data = {}
##    name = "Form Entry Time Report"
##    if clinic_id:
##        user_data = get_users(clinic_id)
##        if user_id:
##            selected_user = [user for user, _ in user_data if user["_id"] == user_id][0]
##            name = "Form Entry Time Report for %s at %s" % (render_user_inline(selected_user), clinic_display_name(clinic_id))
##        else:
##            name = "Form Entry Time Report for %s (%s)" % (clinic_display_name(clinic_id), clinic_id)
##
##    clinic_data = get_clinics()
##    return render_to_response(request, "reports/entrytimes.html",
##                              {"report": {"name": name},
##                               "chart_extras": get_sparkline_extras(data),
##                               "clinic_data": clinic_data,
##                               "user_data": user_data,
##                               "clinic_id": clinic_id,
##                               "user_id": user_id})
#
#
#@require_GET
#def single_chw_summary(request):
#    chw_id = request.GET.get("chw", None)
#    all_chws = get_db().view("phone/cases_sent_to_chws", group=True, group_level=1, reduce=True)
#    chws = []
#    main_chw = None
#    for row in all_chws:
#        chw = CommunityHealthWorker.get(row["key"][0])
#        chws.append(chw)
#        if chw_id == chw.get_id:
#            main_chw = chw
#
#
#    daily_case_data = []
#    total_case_data = []
#    punchcard_url = ""
#    if main_chw:
#        punchcard_url = get_punchcard_url(get_data(main_chw.current_clinic_id, chw_id), width=910)
#
#    return render_to_response(request, "reports/chw_summary.html",
#                              {"report": {"name": "CHW summary%s" % \
#                                          ("" if not main_chw else \
#                                           " for %s (%s)" % (main_chw.formatted_name, main_chw.current_clinic_display))},
#                               "chw_id": chw_id,
#                               "main_chw":    main_chw,
#                               "chws":   chws,
#                               "punchcard_url":    punchcard_url,
#                               })
#
#
#
#@require_GET
#def punchcard(request):
#    # todo
#    clinic_id = request.GET.get("clinic", None)
#    user_id = request.GET.get("user", None)
#    url = None
#    user_data = {}
#    name = "Punchcard Report"
#    if clinic_id:
#        url = get_punchcard_url(get_data(clinic_id, user_id))
#        user_data = get_users(clinic_id)
#        if user_id:
#            selected_user = [user for user, _ in user_data if user["_id"] == user_id][0]
#            name = "Punchcard Report for %s at %s" % (render_user_inline(selected_user), clinic_display_name(clinic_id))
#        else:
#            name = "Punchcard Report for %s (%s)" % (clinic_display_name(clinic_id), clinic_id)
#    clinic_data = get_clinics()
#    return render_to_response(request, "reports/punchcard.html",
#                              {"report": {"name": name},
#                               "chart_url": url,
#                               "clinic_data": clinic_data,
#                               "user_data": user_data,
#                               "clinic_id": clinic_id,
#                               "user_id": user_id})
#
#def unrecorded_referral_list(request):
#    """
#    Clinic able to pull up list of Open Cases that require bookkeeping.
#    Any open case without a follow-up either at the clinic or from the
#    CHW after 6 weeks is given the Outcome: 'Lost Follow Up.' The report
#    also lists cases closed by the CHW and their outcome for the CSW to
#    record in the patient folder.
#    """
#    # display list of open cases but unrecorded cases (referrals)
#    referrals = CReferral.view("reports/closed_unrecorded_referrals")
#    return render_to_response(request, "reports/closed_unrecorded_referrals.html",
#                              {"show_dates": True, "referrals": referrals})
#
#def mortality_register(request):
#    """
#    Enter community mortality register from neighborhood health committee members
#    """
#    def callback(xform, doc):
#        # TODO: add callback
#        return HttpResponseRedirect(reverse("report_list"))
#
#
#    xform = get_xform_by_namespace("http://cidrz.org/bhoma/mortality_register")
#    # TODO: generalize this better
#    preloader_data = {"meta": {"clinic_id": settings.BHOMA_CLINIC_ID,
#                               "user_id":   request.user.get_profile()._id,
#                               "username":  request.user.username}}
#    return xforms_views.play(request, xform.id, callback, preloader_data)
#
#@permission_required("webapp.bhoma_view_pi_reports")
#@wrap_with_dates()
#def under_five_pi(request):
#    """
#    Under five performance indicator report
#    """
#    return _pi_report(request, "reports/under_5_pi")
#
#@permission_required("webapp.bhoma_view_pi_reports")
#@wrap_with_dates()
#def adult_pi(request):
#    """
#    Adult performance indicator report
#    """
#    return _pi_report(request, "reports/adult_pi")
#
#
#@permission_required("webapp.bhoma_view_pi_reports")
#@wrap_with_dates()
#def pregnancy_pi(request):
#    """
#    Pregnancy performance indicator report
#    """
#    return _pi_report(request, "reports/pregnancy_pi")
#
#@permission_required("webapp.bhoma_view_pi_reports")
#@wrap_with_dates()
#def chw_pi(request):
#    """
#    CHW performance indicator report
#    """
#    return _pi_report(request, "reports/chw_pi")
#
#
#def clinic_summary_raw(request, group_level=2):
#    report = get_clinic_summary(group_level)
#    body = render_report(report, template="reports/text/couch_report_raw.txt")
#    return HttpResponse(body, content_type="text/plain")
#
#
#
#def _pi_report(request, view_name):
#    """
#    Generic report engine for the performance indicator reports
#    """
#    results = get_db().view(view_name, group=True, group_level=3,
#                            **_get_keys(request.startdate, request.enddate)).all()
#    report = ReportDisplay.from_pi_view_results(results)
#    return render_to_response(request, "reports/pi_report.html",
#                              {"show_dates": True, "report": report})
#
#def _get_keys(startdate, enddate):
#    # set the start key to the first and the end key to the last of the month
#    startkey = [startdate.year, startdate.month - 1]
#    endkey = [enddate.year, enddate.month - 1, {}]
#    return {"startkey": startkey, "endkey": endkey}