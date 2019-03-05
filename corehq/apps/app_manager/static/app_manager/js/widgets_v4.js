// Note that this file exists only for select2 v4 and it depends on the paginate_releases URL being registered
hqDefine("app_manager/js/widgets_v4", [
    'jquery',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function (
    $,
    assertProperties,
    initialPageData
) {
    var initVersionDropdown = function ($select, options) {
        options = options || {};
        assertProperties.assertRequired(options, [], ['url', 'width']);

        $select.select2({
            ajax: {
                url: options.url || initialPageData.reverse('paginate_releases'),
                dataType: 'json',
                data: function (params) {
                    return {
                        limit: 10,
                        query: params.term,
                        page: params.page,
                    };
                },
                processResults: function (data) {
                    return {
                        results: _.map(data.apps, function (build) {
                            return {
                                id: build.id,
                                text: build.version + ": " + (build.build_comment || gettext("no comment")),
                            };
                        }),
                        pagination: data.pagination,
                    };
                },
            },
            width: options.width || '200px',
        });
    };

    $(function () {
        $(".app-manager-version-dropdown").each(function () {
            initVersionDropdown($(this));
        });
    });

    return {
        initVersionDropdown: initVersionDropdown,
    };
});
