/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/bindingHandlers', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/atwho',
    'atjs',
    'caretjs',
    'bootstrap-daterangepicker/daterangepicker',
    "select2/dist/js/select2.full.min",
], function (
    $,
    ko,
    _,
    atwho
) {
    'use strict';

    ko.bindingHandlers.select2 = {
        init: function (element, valueAccessor, allBindings) {
            var options = ko.utils.unwrapObservable(valueAccessor()),
                ajax = {};

            if (options.url) {
                ajax = {
                    delay: 150,
                    url: options.url,
                    dataType: 'json',
                    type: 'post',
                    data: function (params) {
                        var data = {
                            search: params.term,
                            page: params.page || 1
                        };
                        if (_.isFunction(options.getData)) {
                            data = options.getData(data);
                        }
                        return data;
                    },
                    processResults: function (data) {
                        if (_.isFunction(options.processResults)) {
                            data = options.processResults(data);
                        }
                        return data;
                    },
                    error: function () {
                        if (_.isFunction(options.handleError)) {
                            options.handleError();
                        }
                    },
                };
            }

            $(element).select2({
                minimumInputLength: 0,
                allowClear: true,
                multiple: !!options.multiple,
                placeholder: options.placeholder || gettext("Search..."), // some placeholder required for allowClear
                width: options.width || '100%',
                ajax: ajax,
                templateResult: function (result) {
                    if (_.isFunction(options.templateResult)) {
                        return options.templateResult(result);
                    }
                    return result.text;
                },
                templateSelection: function (selection) {
                    if (_.isFunction(options.templateSelection)) {
                        return options.templateSelection(selection);
                    }
                    return selection.text;
                },
            });
        },
    };

    ko.bindingHandlers.datagridAutocomplete = {
        init: function (element) {
            var $element = $(element);
            if (!$element.atwho) {
                throw new Error("The typeahead binding requires Atwho.js and Caret.js");
            }

            atwho.init($element, {
                atwhoOptions: {
                    displayTpl: function (item) {
                        if (item.case_type) {
                            return '<li><span class="label label-default pull-right">${case_type}</span> ${name}</li>';
                        } else if (item.meta_type) {
                            return '<li><span class="label label-primary pull-right">${meta_type}</span> ${name}</li>';
                        }
                        return '<li>${name}</li>';
                    },
                },
                afterInsert: function () {
                    $element.trigger('textchange');
                },
            });

            $element.on("textchange", function () {
                if ($element.val()) {
                    $element.change();
                }
            });
        },

        update: function (element, valueAccessor) {
            $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
        },
    };

    ko.bindingHandlers.singleDatePicker = {
        update: function (element, valueAccessor) {
            var enable = ko.utils.unwrapObservable(valueAccessor());

            if (enable) {
                $(element).daterangepicker({
                    locale: {
                        format: 'YYYY-MM-DD',
                    },
                    singleDatePicker: true,
                });
            }
        },
    };

});
