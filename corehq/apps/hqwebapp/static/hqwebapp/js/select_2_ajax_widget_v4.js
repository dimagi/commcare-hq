hqDefine("hqwebapp/js/select_2_ajax_widget_v4", [
    'jquery',
    'underscore',
    'select2/dist/js/select2.full.min',
], function ($, _) {
    $(function () {
        $(".hqwebapp-select2-ajax-v4").each(function () {
            var $select = $(this),
                htmlData = $select.data();

            $select.select2({
                multiple: htmlData.multiple,
                escapeMarkup: function (m) { return m; },
                ajax: {
                    url: htmlData.endpoint,
                    dataType: 'json',
                    delay: 100,
                    data: function (params) {
                        return {
                            q: params.term,
                            page_limit: htmlData.pageSize,
                            page: params.page,
                        };
                    },
                    processResults: function (data, params) {
                        var more = (params.page || 1) * htmlData.pageSize < data.total;
                        return {
                            results: data.results,
                            pagination: { more: more },
                        };
                    },
                },
            });

            var initial = htmlData.initial;
            if (initial) {
                if (!_.isArray(initial)) {
                    initial = [initial];
                }
                _.each(initial, function (result) {
                    $select.append(new Option(result.text, result.id));
                });
                $select.val(_.pluck(initial, 'id')).trigger('change');
            }
        });
    });
});
