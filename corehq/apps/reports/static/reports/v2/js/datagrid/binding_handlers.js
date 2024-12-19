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

    var _select2Init = function ($select, options, params) {
        var initialValue;

        $select.select2(params);

        if (!_.isFunction(options.getInitialValue)) {
            return;
        }

        initialValue = options.getInitialValue();

        if (options.multiple) {
            // initializing multi select2s
            if (!_.isObject(initialValue) && !_.isArray(initialValue)) {
                initialValue = [{text: initialValue, id: initialValue}];
            }

            if (!_.isArray(initialValue)) {
                initialValue = [initialValue];
            }

            if (options.url) {
                // only hard load options when async select2 is being used
                _.each(initialValue, function (valObj) {
                    var option = new Option(valObj.text, valObj.id, true, true);
                    $select.append(option);
                });
            }
            $select.trigger('change');
            $select.trigger({type: 'select2:select', params: {data: initialValue}});

        } else {
            // initializing single select2s
            if (_.isObject(initialValue)) {
                if (options.createNodes) { // createNodes needed to get around the ajax load of static options
                    var option = new Option(initialValue.text, initialValue.id, true, true);
                    $select.append(option);
                }
                $select.val(initialValue.id).trigger('change');
            } else {
                $select.val(initialValue).trigger('change');
            }
        }
    };

    ko.bindingHandlers.select2 = {
        init: function (element, valueAccessor) {
            var $select = $(element),
                options = ko.utils.unwrapObservable(valueAccessor()),
                select2Params = {
                    allowClear: options.allowClear,
                    minimumInputLength: 0,
                    multiple: !!options.multiple,
                    placeholder: options.placeholder || gettext("Search..."), // some placeholder required for allowClear
                    width: options.width || '100%',
                    data: options.data,
                    tags: options.tags,
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
                };

            ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                $select.select2('destroy');
            });

            if (options.url) {
                select2Params.ajax = {
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

            if (options.dataUrl) {
                var data = {};
                if (_.isFunction(options.getData)) {
                    data = options.getData(data);
                }
                if (_.isFunction(options.getInitialValue)) {
                    data.currentValue = JSON.stringify(options.getInitialValue());
                }
                if (options.dataObservable) { // this is related to the ajax call below
                    // this is necessary for "pre-loading" the select2 so that
                    // there isn't a blip of a non-select element on the screen
                    // as the static options are fetched from the url specified
                    // in dataUrl
                    select2Params.data = options.dataObservable();
                    options.createNodes = true;
                    _select2Init($select, options, select2Params);
                    options.createNodes = false;
                }

                $.ajax({
                    url: options.dataUrl,
                    method: 'post',
                    dataType: 'json',
                    data: data,
                })
                    .done(function (data) {
                        select2Params.data = data.options;
                        if (options.dataObservable) {
                            $select.select2('destroy');
                            $select.html('');
                            options.dataObservable(data.options);
                        }
                        _select2Init($select, options, select2Params);
                    });
            } else {
                _select2Init($select, options, select2Params);
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

    ko.bindingHandlers.columnResize = {
        /**
         * Makes any table column header resizeable when passed an observable
         * that sets the width of that column in the value accessor.
         *
         * example:
         * <th data-bind="style: { width: width() + 'px' },
         *                columnResize: width"> ... </th>
         *
         * @param element - the column header (th) element
         * @param valueAccessor - observable that sets the width of the column
         */
        init: function (element, valueAccessor) {
            var $column = $(element),
                columnWidth = valueAccessor(),
                $grip = $('<div class="grip">');

            $column.css('position', 'relative');

            $grip
                .css('width', '15px')
                .css('cursor', 'col-resize')
                .css('top', '0')
                .css('right', '0')
                .css('bottom', '0')
                .css('position', 'absolute');

            $grip.on('mousedown', function (e) {
                window.datagridColumnOffset = columnWidth() - e.pageX;
                window.datagridColumnWidth = columnWidth;
            });

            $column.append($grip);
        },
    };

    $(document).on('mousemove', function (e) {
        // needed for columnResize bindingHandler
        if (window.datagridColumnWidth) {
            window.datagridColumnWidth(window.datagridColumnOffset + e.pageX);
        }
    });

    $(document).on('mouseup', function () {
        // needed for columnResize bindingHandler
        window.datagridColumnWidth = undefined;
    });

});
