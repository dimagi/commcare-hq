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
        $filter.select2({  // TODO: test
            ajax: {
                url: $filter.data('url'),
                type: 'POST',
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    return {
                        q: params.term,
                        page: params.page,  // TODO: does params really have a page property?
                        handler: $filter.data('handler'),
                        action: $filter.data('action'),
                    };
                },
                processResults: function (data, params) {
                    if (data.success) {
                        var limit = data.limit;
                        var hasMore = (params.page * limit) < data.total;
                        return {
                            results: data.items,
                            more: hasMore,
                        };
                    }
                },
                width: '100%',
            },
            allowClear: true,
            placeholder: " ",
            // TODO
            /*initSelection: function (elem, callback) {
                var val = $(elem).val();
                callback({
                    id: val,
                    text: val,
                });
            },*/
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
        $filter.select2({   // TODO: test
            ajax: {
                url: data.endpoint,
                dataType: 'json',
                data: function (params) {
                    return {
                        q: params.term,
                        page_limit: 10,
                        page: params.page,  // TODO: is this real?
                    };
                },
                processResults: function (data, params) {
                    var more = data.more || (params.page * 10) < data.total;
                    return {results: data.results, more: more};
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
