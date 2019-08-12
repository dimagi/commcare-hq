/* global interpolate */
hqDefine('users/js/filtered_download', function () {
    function getFilters() {
        return {
            'role_id': $("#id_role_id").val(),
            'search_string': $("#id_search_string").val(),
            'location_id': $("[name=location_id]").val(),
        };
    }

    $(function () {
        var prevFilters = getFilters();
        var countUsersUrl = hqImport('hqwebapp/js/initial_page_data').get('count_users_url');
        setInterval(function () {
            var currentFilters = getFilters();
            if (!_.isEqual(currentFilters, prevFilters)) {
                $.get({
                    url: countUsersUrl,
                    data: currentFilters,
                    success: function (data) {
                        var count = data['count'];
                        var text = ngettext("Download %s User", "Download %s Users", count);
                        text = interpolate(text, [count]);
                        $('.submit_button').text(text);
                    },
                    error: function () {
                        alert("Error determining number of matching users");
                    },
                });
            }
            prevFilters = currentFilters;
        }, 1000);
    });
});
