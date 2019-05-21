/**
 * The basic single and multi option filters.
 */
hqDefine("reports/js/filters/select2s", [
    'jquery',
    'knockout',
    'select2/dist/js/select2.full.min',
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
                delay: 250,
                data: function (params) {
                    return {
                        q: params.term,
                        page: params.page,
                        handler: $filter.data('handler'),
                        action: $filter.data('action'),
                    };
                },
                processResults: function (data, params) {
                    params.page = params.page || 1;
                    if (data.success) {
                        var limit = data.limit;
                        var hasMore = (params.page * limit) < data.total;
                        return {
                            results: data.items,
                            pagination: {
                                more: hasMore,
                            },
                        };
                    }
                },
                width: '100%',
            },
            allowClear: true,
            placeholder: " ",
        });
        var initial = $filter.data("selected");
        if (initial) {
            $filter.append(new Option(initial.text, initial.id));
            $filter.val(initial.id);
            $filter.trigger('change.select2');
        }
    };

    var initMulti = function (el) {
        var $filter = $(el),
            data = $filter.data();
        $filter.parent().koApplyBindings({
            select_params: data.options,
            current_selection: ko.observableArray(data.selected),
        });

        if (!data.endpoint) {
            $filter.select2({
                width: '100%',
            });
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
        var pageLimit = 10;
        $filter.select2({
            ajax: {
                url: data.endpoint,
                dataType: 'json',
                data: function (params) {
                    return {
                        q: params.term,
                        page_limit: pageLimit,
                        page: params.page,
                    };
                },
                processResults: function (data, params) {
                    // TODO: params.page should be || 1 everywhere probably
                    params.page = params.page || 1;
                    var more = data.more || data.pagination && data.pagination.more || (params.page * pageLimit) < data.total;
                    return {
                        results: data.results,
                        pagination: {
                            more: more,
                        },
                    };
                },
            },
            multiple: true,
            escapeMarkup: function (m) { return m; },
            width: '100%',
        });

        if (data.selected && data.selected.length) {
            _.each(data.selected, function (item) {
                $filter.append(new Option(item.text, item.id));
            });
            $filter.trigger({type: 'select2:select', params: { data: data.selected }});
            $filter.val(_.map(data.selected, function (item) { return item.id }));
            $filter.trigger('change.select2');
        }
    };

    return {
        initSingle: initSingle,
        initSinglePaginated: initSinglePaginated,
        initMulti: initMulti,
    };
});
