"use strict";
hqDefine("hqwebapp/js/select_2_ajax_widget", [
    'jquery',
    'underscore',
    'select2/dist/js/select2.full.min',
], function ($, _) {
    $(function () {
        $(".hqwebapp-select2-ajax").each(function () {
            var $select = $(this),
                htmlData = $select.data();

            $select.select2({
                multiple: htmlData.multiple,
                width: '100%',
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

            // Select initial value if one was provided, which could be a single object,
            // formatted as { id: 1, text: 'thing' }, or an array of such objects
            var initial = htmlData.initial;
            if (initial) {
                if (!_.isArray(initial)) {
                    initial = [initial];
                }

                // Add a DOM option for each value, which select2 will pick up on change
                _.each(initial, function (result) {
                    $select.append(new Option(result.text, result.id));
                });

                // Set the actual value; using an array works for both single and multiple selects
                $select.val(_.pluck(initial, 'id'));

                $select.trigger('change');
            }
        });
    });
});
