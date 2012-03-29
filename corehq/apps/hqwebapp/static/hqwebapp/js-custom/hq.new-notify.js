$(function() {
    var new_reports_cookie_name = 'CommCareHQ_ReportsRedesign1.0',
        $redesignNotice = $('<div />').attr("id","new-report-design-announcement");

    if(! $.cookie(new_reports_cookie_name)) {
        $redesignNotice.addClass("alert").addClass("alert-info").addClass("alert-full");
        var $closeIcon = $('<a />').addClass("close").attr("data-dismiss", "alert");
        $closeIcon.attr("href", "#").html("&times;");
        $redesignNotice.append($closeIcon);
        $redesignNotice.append($('<strong />').text("Welcome to CommCare HQ's new look!"));
        $redesignNotice.append(" Reports has been redesigned, and the rest of the pages are on their way. We hope you enjoy these changes.");
        $(".hq-page-header-container").prepend($redesignNotice);

        $('#new-report-design-announcement').bind('closed', function () {
            $.cookie(new_reports_cookie_name, 'viewed', {path: "/"});
        });
    }
});