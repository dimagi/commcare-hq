hqDefine('hqcase/js/explode_cases', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
], function (
    $,
    ko,
    initialPageData
) {
    $(function () {
        $('#explode').koApplyBindings({
            factor: ko.observable(''),
            user_id: ko.observable(''),
        });
        $('#explode-user_id').select2({
            ajax: {
                url: initialPageData.reverse('users_select2_options'),
                type: 'POST',
                datatype: 'json',
                quietMills: 250,
                data: function (term, page) {
                    return {
                        q: term,
                        page: page,
                    };
                },
                results: function (data, page) {
                    if (data.success) {
                        var limit = data.limit;
                        var hasMore = (page * limit) < data.total;
                        return {
                            results: data.items,
                            more: hasMore,
                        };
                    }
                },
            },
        });
    });
});
