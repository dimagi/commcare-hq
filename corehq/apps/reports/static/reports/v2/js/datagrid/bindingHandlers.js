/**
 * todo add docstring
 */

hqDefine('reports/v2/js/datagrid/bindingHandlers', [
    'jquery',
    'knockout',
    'hqwebapp/js/atwho',
    'atjs',
    'caretjs',
    'bootstrap-daterangepicker/daterangepicker',
], function (
    $,
    ko,
    atwho
) {
    'use strict';

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
