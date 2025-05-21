import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import "select2/dist/js/select2.full.min";

$(function () {
    $('#explode').koApplyBindings({
        factor: ko.observable(''),
        user_id: ko.observable(''),
    });
    $('#explode-user_id').select2({
        ajax: {
            url: initialPageData.reverse('users_select2_options'),
            type: 'POST',
            dataType: 'json',
            quietMills: 250,
            data: function (params) {
                return {
                    q: params.term,
                    page: params.page,
                };
            },
            processResults: function (data, page) {
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
