hqDefine("hqwebapp/js/select_2_ajax_widget", [
    'jquery',
    'select2/dist/js/select2.full.min',
], function ($) {
    $(function () {
        $(".hqwebapp-select2-ajax").each(function () {
            var $select = $(this),
                data = $select.data();
            $select.select2({
                multiple: data.multiple,
                ajax: {
                    url: data.endpoint,
                    dataType: 'json',
                    data: function (term, page) {
                        return {
                            q: term,
                            page_limit: data.pageSize,
                            page: page,
                        };
                    },
                    results: function (data, page) {
                        var more = (page * data.pageSize) < data.total;
                        return {results: data.results, more: more};
                    },
                },
                initSelection: function (element, callback) {
                    /*
                        Initialize the selection based on the value of the element select2 is attached to.
                        Essentially this is an id->object mapping function.
                    */
                    // Note that if you want to use `val("someid")` with this select2, then this function needs to
                    // be improved because this function doesn't actually look at the element's value.
                    // You can use `data({"id": "someid", "text": "sometext"})` as is though.

                    if (data.initial && data.initial.length) {
                        callback(data.initial);
                    }
                },
                escapeMarkup: function (m) { return m; },
            }).select2('val', data.initial);
        });
    });
});
