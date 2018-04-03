hqDefine("reports/js/edit_submission", function() {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        GMAPS_API_KEY = initialPageData('maps_api_key'); // maps api is a global variable depended on by touchforms
        var edit_context = initialPageData("edit_context");
        var uses_sql_backend = initialPageData("use_sqlite_backend");
        var username = initialPageData("username");
        var edit_formplayer = initialPageData("edit_formplayer");
        var restoreAs = edit_context.sessionData.username;
        $('#edit-container').inlineFormplayer({
            formUrl: edit_context.formUrl,
            submitUrl: edit_context.submitUrl,
            sessionData: edit_context.sessionData,
            uses_sql_backend: uses_sql_backend,
            formplayerEnabled: edit_formplayer,
            domain: edit_context.domain,
            username: username,
            restoreAs: restoreAs,
            onsubmit: function () {
                window.location.href = edit_context.returnUrl;
            },
            onload: function () {
            }
        });
    });
});
