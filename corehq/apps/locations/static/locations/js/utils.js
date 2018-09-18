hqDefine('locations/js/utils', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData
) {
    var show_inactive, location_search_url, locs;

    var enableLocationSearchSelect = function () {
        $('#location_search_select').select2({
            ajax: {
                url: location_search_url,
                dataType: 'json',
                data: function (params) {
                    return {
                        q: params.term,
                        page_limit: 10,
                        page: params.page,
                        show_inactive: show_inactive,
                    };
                },
                processResults: function (data, params) {
                    var more = data.more || (params.page * 10) < data.total;
                    return { results: data.results, more: more };
                },
            },
        });
    };

    var reloadLocationSearchSelect = function () {
        $('#location_search_select').select2('val', null);
        enableLocationSearchSelect();
    };

    var clearLocationSelection = function (tree_model) {
        reloadLocationSearchSelect();
        tree_model.load(locs);
    };

    $(function () {
        show_inactive = initialPageData.get('show_inactive');
        location_search_url = initialPageData.reverse('location_search');
        locs = initialPageData.get('locations');
    });

    return {
        enableLocationSearchSelect: enableLocationSearchSelect,
        reloadLocationSearchSelect: reloadLocationSearchSelect,
        clearLocationSelection: clearLocationSelection,
    };
});
