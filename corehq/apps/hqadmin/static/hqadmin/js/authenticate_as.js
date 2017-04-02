/* globals hqDefine */
hqDefine('hqadmin/js/authenticate_as.js', function () {
    $(function() {
        $('#id_username, #id_domain').change(function() {
            var username = $('#id_username').val(),
                domain = $('#id_domain').val();
    
            var action = hqImport('hqwebapp/js/initial_page_data.js').get('url') + username + '/';
            if (domain) {
                action += domain + '/';
            }
    
            $('#auth-as-form').attr('action', action);
        });
    });
});
