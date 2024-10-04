"use strict";
hqDefine('hqwebapp/js/multiselect_utils', [
    "jquery",
    "knockout",
    "underscore",
    "hqwebapp/js/assert_properties",
    "multiselect/js/jquery.multi-select",
    "quicksearch/dist/jquery.quicksearch.min",
], function (
    $,
    ko,
    _,
    assertProperties
) {
    var self = {};

    var _renderHeader = function (title, action, search) {
        // Since action and search are created from _renderAction() and _renderSearch()
        // and the variables the functions are esacaped so it would be safe to use them with <%=
        var header = _.template('<div class="ms-header"><%- headerTitle %><%= actionButton %></div><%= searchInput %>');
        return header({
            headerTitle: title,
            actionButton: action || '',
            searchInput: search || '',
        });
    };

    var _renderAction = function (buttonId, buttonClass, buttonIcon, text, disabled = false) {
        var action = _.template(
            '<button class="btn <%-actionButtonClass %> btn-xs <%- floatClass %>" id="<%- actionButtonId %>" <% if (actionDisabled) { %> disabled <% } %>>' +
                '<i class="<%- actionButtonIcon %>"></i> <%- actionButtonText %>' +
            '</button>'
        );
        return action({
            actionButtonId: buttonId,
            actionButtonClass: buttonClass,
            actionButtonIcon: buttonIcon,
            actionButtonText: text,
            actionDisabled: disabled,
            floatClass: window.USE_BOOTSTRAP5 ? "float-end" : "pull-right",
        });
    };

    var _renderSearch = function (inputId, placeholder) {
        var inputGroupTextClass = (window.USE_BOOTSTRAP5) ? "input-group-text" : "input-group-addon",
            input = _.template(
                '<div class="input-group ms-input-group">' +
                    '<span class="' + inputGroupTextClass + '">' +
                        '<i class="fa fa-search"></i>' +
                    '</span>' +
                    '<input type="search" class="form-control search-input" id="<%- searchInputId %>" autocomplete="off" placeholder="<%- searchInputPlaceholder %>" />' +
                '</div>'
            );
        return input({
            searchInputId: inputId,
            searchInputPlaceholder: placeholder,
        });
    };

    /**
     * Given an element, configures multiselect functionality based on the multiselect.js library
     * @param {object} properties - a key-value object that expects the following optional keys:
     * selectableHeaderTitle -  String title for items yet to be selected. Defaults to "Items".
     * selectedHeaderTitle - String for selected items title. Defaults to "Selected items".
     * searchItemTitle - String for search bar placeholder title. Defaults to "Search items".
     * willSelectAllListener - Function to call before the multiselect processes the Add All action.
     * disableModifyAllActions - Boolean value to enable/disable Add All and Remove All buttons. Defaults to false.
     */
    self.createFullMultiselectWidget = function (elementOrId, properties) {
        assertProperties.assert(properties, [], ['selectableHeaderTitle', 'selectedHeaderTitle', 'searchItemTitle', 'willSelectAllListener', 'disableModifyAllActions']);
        var selectableHeaderTitle = properties.selectableHeaderTitle || gettext("Items");
        var selectedHeaderTitle = properties.selectedHeaderTitle || gettext("Selected items");
        var searchItemTitle = properties.searchItemTitle || gettext("Search items");
        var willSelectAllListener = properties.willSelectAllListener;
        var disableModifyAllActions = properties['disableModifyAllActions'] || false;

        var $element = _.isString(elementOrId) ? $('#' + elementOrId) : $(elementOrId),
            baseId = _.isString(elementOrId) ? elementOrId : "multiselect-" + String(Math.random()).substring(2),
            selectAllId = baseId + '-select-all',
            removeAllId = baseId + '-remove-all',
            searchSelectableId = baseId + '-search-selectable',
            searchSelectedId = baseId + '-search-selected',
            defaultBtnClass = (window.USE_BOOTSTRAP5) ? 'btn-outline-primary btn-sm' : 'btn-default';

        $element.multiSelect({
            selectableHeader: _renderHeader(
                selectableHeaderTitle,
                _renderAction(selectAllId, defaultBtnClass, 'fa fa-plus', gettext("Add All"), disableModifyAllActions),
                _renderSearch(searchSelectableId, searchItemTitle)
            ),
            selectionHeader: _renderHeader(
                selectedHeaderTitle,
                _renderAction(removeAllId, defaultBtnClass, 'fa fa-remove', gettext("Remove All"), disableModifyAllActions),
                _renderSearch(searchSelectedId, searchItemTitle)
            ),
            afterInit: function () {
                var that = this,
                    $selectableSearch = $('#' + searchSelectableId),
                    $selectionSearch = $('#' + searchSelectedId),
                    selectableSearchString = '#' + that.$container.attr('id') + ' .ms-elem-selectable:not(.ms-selected)',
                    selectionSearchString = '#' + that.$container.attr('id') + ' .ms-elem-selection.ms-selected';

                that.search_left = $selectableSearch.quicksearch(selectableSearchString)
                    .on('keydown', function (e) {
                        if (e.which === 40) {  // down arrow, was recommended by loudev docs
                            that.$selectableUl.focus();
                            return false;
                        }
                    })
                    .on('keyup change search input', function () {
                    // disable add all functionality so that user is not confused
                        if (that.search_left.val().length > 0) {
                            $('#' + selectAllId).addClass('disabled').prop('disabled', true);
                        } else {
                            if (!disableModifyAllActions) {
                                $('#' + selectAllId).removeClass('disabled').prop('disabled', false);
                            }
                        }
                    });

                that.search_right = $selectionSearch.quicksearch(selectionSearchString)
                    .on('keydown', function (e) {
                        if (e.which === 40) {  // down arrow, was recommended by loudev docs
                            that.$selectionUl.focus();
                            return false;
                        }
                    })
                    .on('keyup change search input', function () {
                    // disable remove all functionality so that user is not confused
                        if (that.search_right.val().length > 0) {
                            $('#' + removeAllId).addClass('disabled').prop('disabled', true);
                        } else if (!disableModifyAllActions) {
                            $('#' + removeAllId).removeClass('disabled').prop('disabled', false);
                        }
                    });
            },
            afterSelect: function () {
                this.search_left.cache();
                // remove search option so that user doesn't get confused
                this.search_right.val('').search('');
                if (!disableModifyAllActions) {
                    $('#' + removeAllId).removeClass('disabled').prop('disabled', false);
                }
                this.search_right.cache();
            },
            afterDeselect: function () {
                // remove search option so that user doesn't get confused
                this.search_left.val('').search('');
                if (!disableModifyAllActions) {
                    $('#' + selectAllId).removeClass('disabled').prop('disabled', false);
                }
                this.search_left.cache();
                this.search_right.cache();
            },
        });

        $('#' + selectAllId).click(function () {
            if (willSelectAllListener) {
                willSelectAllListener();
            }
            $element.multiSelect('select_all');
            return false;
        });
        $('#' + removeAllId).click(function () {
            $element.multiSelect('deselect_all');
            return false;
        });
    };

    self.rebuildMultiselect = function (elementOrId, multiselectProperties) {
        var $element = _.isString(elementOrId) ? $('#' + elementOrId) : $(elementOrId);
        // multiSelect('refresh') breaks existing click handlers, so the alternative is to destroy and rebuild
        $element.multiSelect('destroy');
        self.createFullMultiselectWidget(elementOrId, multiselectProperties);
    };

    /*
     * A custom binding for setting multiselect properties and additional knockout bindings
     * The only dynamic part of this binding are the options
     * For a list of configurable multiselect properties, see http://loudev.com/ under Options
     * properties - a dictionary of properties used by the multiselect element (see createFullMultiselectWidget above)
     * options - an observable array of option elements (only supports array of strings)
     * didUpdateListener - method to invoke when the multiselect updates
     */
    ko.bindingHandlers.multiselect = {
        init: function (element, valueAccessor) {
            var model = valueAccessor();
            assertProperties.assert(model, [], ['properties', 'options', 'didUpdateListener']);
            self.createFullMultiselectWidget(element, model.properties);

            if (model.options) {
                // apply bindings after the multiselect has been setup
                ko.applyBindingsToNode(element, {options: model.options});
            }
        },
        update: function (element, valueAccessor) {
            var model = valueAccessor();
            assertProperties.assert(model, [], ['properties', 'options', 'didUpdateListener']);
            if (model.options) {
                // have to access the observable to get the `update` method to fire on changes to options
                ko.unwrap(model.options());
            }

            self.rebuildMultiselect(element, model.properties);
            if (model.didUpdateListener) {
                model.didUpdateListener();
            }
        },
    };

    return self;
});
