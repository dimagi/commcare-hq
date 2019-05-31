/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/binding_handlers', [
    'jquery',
    'knockout',
    'underscore',
    'bootstrap-daterangepicker/daterangepicker',
    "select2/dist/js/select2.full.min",
], function (
    $,
    ko,
    _
) {
    'use strict';

    ko.bindingHandlers.select2 = {
        init: function (element, valueAccessor) {
            var $select = $(element),
                options = ko.utils.unwrapObservable(valueAccessor()),
                ajax = {};

            ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                $select.select2('destroy');
            });

            if (options.url) {
                ajax = {
                    delay: options.delay || 150,
                    url: options.url,
                    dataType: 'json',
                    type: 'post',
                    data: function (params) {
                        var data = {
                            search: params.term,
                            page: params.page || 1,
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

            $select.select2({
                minimumInputLength: 0,
                allowClear: true,
                multiple: !!options.multiple,
                placeholder: options.placeholder || gettext("Search..."), // some placeholder required for allowClear
                width: options.width || '100%',
                data: options.data,
                ajax: ajax,
                templateResult: function (result) {
                    if (_.isFunction(options.templateResult)) {
                        return options.templateResult(result);
                    }
                    if (result.labelText) {
                        var $label = $('<span class="label pull-right"></span>')
                                     .addClass(result.labelStyle)
                                     .text(result.labelText);
                        return $('<span>' + result.text + '</span>').append($label);
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

            if (_.isFunction(options.getInitialValue) && (_.isObject(options.getInitialValue()) || _.isArray(options.getInitialValue()))) {
                // https://select2.org/programmatic-control/add-select-clear-items#preselecting-options-in-an-remotely-sourced-ajax-select2
                var initialValue = options.getInitialValue();
                if (!_.isArray(options.getInitialValue())) {
                    initialValue = [initialValue];
                }
                _.each(initialValue, function (valObj) {
                    var option = new Option(valObj.text, valObj.id, true, true);
                    $select.append(option);
                });
                $select.trigger('change');
                $select.trigger({type: 'select2:select', params: {data: initialValue}});
            }

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
