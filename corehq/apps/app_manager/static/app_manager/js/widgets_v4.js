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
        assertProperties.assert(options, [], ['url', 'width', 'idValue', 'initialValue', 'extraValues',
            'onlyShowReleased']);
        var idValue = options.idValue || 'id';

        $select.select2({
            ajax: {
                url: options.url || initialPageData.reverse('paginate_releases'),
                dataType: 'json',
                data: function (params) {
                    return {
                        limit: 10,
                        query: params.term,
                        page: params.page,
                        only_show_released: options.onlyShowReleased,
                    };
                },
                processResults: function (data) {
                    var results = _.map(data.apps, function (build) {
                        return {
                            id: build[idValue],
                            text: build.version + ": " + (build.build_comment || gettext("no comment")),
                        };
                    });
                    if (options.extraValues) {
                        results = Array.prototype.concat(options.extraValues, results);
                    }
                    return {
                        results: results,
                        pagination: data.pagination,
                    };
                },
            },
            templateSelection: function (data) {
                // Only show the version number when selected
                return data.text.split(": ")[0];
            },
            width: options.width || '200px',
        });

        if (options.initialValue) {
            // https://select2.org/programmatic-control/add-select-clear-items#preselecting-options-in-an-remotely-sourced-ajax-select2
            var option = new Option(options.initialValue.text, options.initialValue.id, true, true);
            $select.append(option).trigger('change');
            $select.trigger({type: 'select2:select', params: {data: options.initialValue}});
        }
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
