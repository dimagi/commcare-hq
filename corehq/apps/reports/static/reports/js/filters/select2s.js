/**
 * The basic single and multi option filters.
 */
hqDefine("reports/js/filters/select2s", [
    'jquery',
    'knockout',
    'select2-3.5.2-legacy/select2',
], function (
    $,
    ko
) {
    var initSingle = function (el) {
        var $filter = $(el);
        $filter.parent().koApplyBindings({
            select_params: $filter.data("selectOptions"),
            current_selection: ko.observable($filter.data("selected")),
        });
        $filter.select2();
    };

    var initSinglePaginated = function (el) {
        var $filter = $(el);
        $filter.select2({
            ajax: {
                url: $filter.data('url'),
                type: 'POST',
                dataType: 'json',
                quietMills: 250,
                data: function (term, page) {
                    return {
                        q: term,
                        page: page,
                        handler: $filter.data('handler'),
                        action: $filter.data('action'),
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
            allowClear: true,
            initSelection: function (elem, callback) {
                var val = $(elem).val();
                callback({
                    id: val,
                    text: val,
                });
            },
        });
    };

    var initMulti = function (el) {
        var $filter = $(el),
            data = $filter.data();
        $filter.parent().koApplyBindings({
            select_params: data.options,
            current_selection: ko.observableArray(data.selected),
        });

        if (!data.endpoint) {
            $filter.select2();
            return;
        }

        /*
         * If there's an endpoint, this is a select2 widget using a
         * remote endpoint for paginated, infinite scrolling options.
         * Check out EmwfOptionsView as an example
         * The endpoint should return json in this form:
         * {
         *     "total": 9935,
         *     "results": [
         *         {
         *             "text": "kingofthebritains (Arthur Pendragon)",
         *             "id": "a242ly1b392b270qp"
         *         },
         *         {
         *             "text": "thebrave (Sir Lancelot)",
         *             "id": "92b270qpa242ly1b3"
         *         }
         *      ]
         * }
         */
        $filter.select2({
            ajax: {
                url: data.endpoint,
                dataType: 'json',
                data: function (term, page) {
                    return {
                        q: term,
                        page_limit: 10,
                        page: page,
                    };
                },
                results: function (data, page) {
                    var more = data.more || (page * 10) < data.total;
                    return {results: data.results, more: more};
                },
            },
            initSelection: function (element, callback) {
                callback(data.selected);
            },
            multiple: true,
            escapeMarkup: function (m) { return m; },
        }).select2('val', data.selected);
    };

    return {
        initSingle: initSingle,
        initSinglePaginated: initSinglePaginated,
        initMulti: initMulti,
    };
});
