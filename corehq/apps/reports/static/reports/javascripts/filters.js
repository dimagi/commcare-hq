/* global hqDefine, jQuery */
hqDefine("reports/javascripts/filters", ['jquery', 'knockout', 'underscore', 'select2'], function($, ko, _) {
    "use strict";
    var initSingleOption = function() {
        _.each($(".reports-filters-single-option"), function(el) {
            var initialData = $.parseJSON($(el).find(".initial-data").text());
            if (initialData.pagination) {
                var $input = $(el).find("input");
                $input.select2({
                    ajax: {
                        url: initialData.url,
                        type: 'POST',
                        dataType: 'json',
                        quietMills: 250,
                        data: function (term, page) {
                            return {
                                q: term,
                                page: page,
                                handler: initialData.handler,
                                action: initialData.action,
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
                            } else {
                                console.log(data.error);    // eslint-disable-line no-console
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
            } else {
                var $select = $(el).find("select");
                $select.parent().koApplyBindings({
                    select_params: initialData.selectOptions,
                    current_selection: ko.observable(initialData.selectCurrent),
                });
                $select.select2();
            }
        });
    };

    return {
        init: function() {
            initSingleOption();
        },
    };
});
