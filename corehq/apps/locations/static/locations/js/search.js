hqDefine('locations/js/search', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData
) {
    let showInactive, locationSearchUrl, locs;

    var enableLocationSearchSelect = function () {
        var $select = $('#location_search_select');
        $select.select2({
            ajax: {
                url: locationSearchUrl,
                dataType: 'json',
                data: function (params) {
                    return {
                        q: params.term,
                        page_limit: 10,
                        page: params.page,
                        show_inactive: showInactive,
                    };
                },
                processResults: function (data, params) {
                    params.page = params.page || 1;
                    var more = data.more || (params.page * 10) < data.total;
                    return { results: data.results, pagination: { more: more } };
                },
            },
        });
        var initialValue = initialPageData.get('locationSearchSelectInitialValue');
        if (initialValue) {
            // https://select2.org/programmatic-control/add-select-clear-items#preselecting-options-in-an-remotely-sourced-ajax-select2
            var option = new Option(initialValue.text, initialValue.id, true, true);
            $select.append(option).trigger('change');
            $select.trigger({type: 'select2:select', params: {data: initialValue}});
        }
    };

    var reloadLocationSearchSelect = function () {
        $('#location_search_select').val(null).trigger('change');
        enableLocationSearchSelect();
    };

    var clearLocationSelection = function (treeModel) {
        reloadLocationSearchSelect();
        treeModel.load(locs);
    };

    $(function () {
        showInactive = initialPageData.get('show_inactive');
        locationSearchUrl = initialPageData.reverse('location_search');
        locs = initialPageData.get('locations');
        enableLocationSearchSelect();
    });

    return {
        reloadLocationSearchSelect: reloadLocationSearchSelect,
        clearLocationSelection: clearLocationSelection,
    };
});
