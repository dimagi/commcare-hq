hqDefine('users/js/filtered_download', function () {
    $(function () {
        var prevFilters = {
            'role_id': $("#id_role_id").val(),
            'search_string': $("#id_search_string").val(),
        };
        var countUsersUrl = hqImport('hqwebapp/js/initial_page_data').get('count_users_url');
        setInterval(function(){
            var currentFilters = {
                'role_id': $("#id_role_id").val(),
                'search_string': $("#id_search_string").val(),
            };
            if (prevFilters.role_id !== currentFilters.role_id || prevFilters.search_string !== currentFilters.search_string) {
                $.get({
                    url: countUsersUrl,
                    data: currentFilters,
                    success: function(data) {
                        var count = data['count'];
                        var text = django.ngettext("Download %s User", "Download %s Users", count);
                        text = interpolate(text, [count]);
                        $('.submit_button').text(text);
                    },
                    error: function(e) {
                        alert("Error determining number of matching users");
                    },
                });
            }
            prevFilters = currentFilters;
        }, 1000);
    });
});
