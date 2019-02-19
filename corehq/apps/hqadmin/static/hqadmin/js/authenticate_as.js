hqDefine('hqadmin/js/authenticate_as', [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    $(function () {
        $('#id_username, #id_domain').change(function () {
            var username = $('#id_username').val(),
                domain = $('#id_domain').val();
            // add username and domain to get those tracked in auditsaudau
            var action = initialPageData.get('url') + username + '/';
            if (domain) {
                action += domain + '/';
            }

            $('#auth-as-form').attr('action', action);
        });
    });
});
