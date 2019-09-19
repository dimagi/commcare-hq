hqDefine('users/js/filtered_download', [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',      // role selection
    'locations/js/widgets',     // location search
], function (
    $,
    _,
    initialPageData
) {
    function getFilters() {
        return {
            'role_id': $("#id_role_id").val(),
            'search_string': $("#id_search_string").val(),
            'location_id': $("[name=location_id]").val(),
        };
    }

    $(function () {
        var prevFilters = getFilters();
        var countUsersUrl = initialPageData.get('count_users_url');
        setInterval(function () {
            var currentFilters = getFilters();
            if (!_.isEqual(currentFilters, prevFilters)) {
                $.get({
                    url: countUsersUrl,
                    data: currentFilters,
                    success: function (data) {
                        var count = data.count;
                        var template = count === 1 ? gettext("Download <%= count %> user") : gettext("Download <%= count %> users");
                        $('.submit_button').text(_.template(template)({count: count}));
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
