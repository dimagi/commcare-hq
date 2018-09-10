hqDefine("reports/js/edit_submission", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        window.GMAPS_API_KEY = initialPageData('maps_api_key'); // maps api is a global variable depended on by touchforms
        var editContext = initialPageData("edit_context");
        var username = initialPageData("username");
        var restoreAs = editContext.sessionData.username;
        $('#edit-container').inlineFormplayer({
            formUrl: editContext.formUrl,
            submitUrl: editContext.submitUrl,
            sessionData: editContext.sessionData,
            uses_sql_backend: initialPageData("use_sqlite_backend"),
            formplayerEnabled: initialPageData("edit_formplayer"),
            domain: editContext.domain,
            username: username,
            restoreAs: restoreAs,
            onsubmit: function () {
                window.location.href = editContext.returnUrl;
            },
            onload: function () {
            },
        });
    });
});
