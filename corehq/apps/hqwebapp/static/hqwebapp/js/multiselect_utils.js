hqDefine('hqwebapp/js/multiselect_utils', [
    "jquery",
    "knockout",
    "underscore",
    "multiselect/js/jquery.multi-select",
    "quicksearch/dist/jquery.quicksearch.min",
], function (
    $,
    ko,
    _
) {
    var multiselect_utils = {};

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

    var _renderAction = function (buttonId, buttonClass, buttonIcon, text) {
        var action = _.template(
            '<button class="btn <%-actionButtonClass %> btn-xs pull-right" id="<%- actionButtonId %>">' +
                '<i class="<%- actionButtonIcon %>"></i> <%- actionButtonText %>' +
            '</button>'
        );
        return action({
            actionButtonId: buttonId,
            actionButtonClass: buttonClass,
            actionButtonIcon: buttonIcon,
            actionButtonText: text,
        });
    };

    var _renderSearch = function (inputId, placeholder) {
        var input = _.template(
            '<div class="input-group ms-input-group">' +
                '<span class="input-group-addon">' +
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

    multiselect_utils.createFullMultiselectWidget = function (
        elementOrId,
        selectableHeaderTitle,
        selectedHeaderTitle,
        searchItemTitle,
        values
    ) {
        var $element = _.isString(elementOrId) ? $('#' + elementOrId) : $(elementOrId),
            baseId = _.isString(elementOrId) ? elementOrId : "multiselect-" + String(Math.random()).substring(2),
            selectAllId = baseId + '-select-all',
            removeAllId = baseId + '-remove-all',
            searchSelectableId = baseId + '-search-selectable',
            searchSelectedId = baseId + '-search-selected';

        $element.multiSelect({
            selectableHeader: _renderHeader(
                selectableHeaderTitle,
                _renderAction(selectAllId, 'btn-default', 'fa fa-plus', gettext("Add All")),
                _renderSearch(searchSelectableId, searchItemTitle)
            ),
            selectionHeader: _renderHeader(
                selectedHeaderTitle,
                _renderAction(removeAllId, 'btn-default', 'fa fa-remove', gettext("Remove All")),
                _renderSearch(searchSelectedId, searchItemTitle)
            ),
            afterInit: function () {
                _.each(values, (item) => {
                    if (typeof item !== 'object') {
                        item = { value: item, text: item};
                    }
                    $element.multiSelect('addOption', item);
                });

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
                            $('#' + selectAllId).removeClass('disabled').prop('disabled', false);
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
                        } else {
                            $('#' + removeAllId).removeClass('disabled').prop('disabled', false);
                        }
                    });
            },
            afterSelect: function () {
                this.search_left.cache();
                // remove search option so that user doesn't get confused
                this.search_right.val('').search('');
                $('#' + removeAllId).removeClass('disabled').prop('disabled', false);
                this.search_right.cache();
            },
            afterDeselect: function () {
                // remove search option so that user doesn't get confused
                this.search_left.val('').search('');
                $('#' + selectAllId).removeClass('disabled').prop('disabled', false);
                this.search_left.cache();
                this.search_right.cache();
            },
        });

        $('#' + selectAllId).click(function () {
            $element.multiSelect('select_all');
            return false;
        });
        $('#' + removeAllId).click(function () {
            $element.multiSelect('deselect_all');
            return false;
        });
    };

    /*
     * A custom binding for setting multiselect properties in knockout content.
     * This binding does not handle dynamic properties, but could be extended to do so.
     * For a list of available options, see http://loudev.com/ under Options
     */
    ko.bindingHandlers.multiselect = {
        init: function (element, valueAccessor) {
            var options = valueAccessor();
            multiselect_utils.createFullMultiselectWidget(
                element,
                options.selectableHeaderTitle || gettext("Items"),
                options.selectedHeaderTitle || gettext("Selected items"),
                options.searchItemTitle || gettext("Search items"),
                ko.unwrap(options.values) || []
            );
        },
    };

    /*
    * A custom binding for dynamically updating select options when using the multiselect binding
    * Replace the `options` binding with `multiselectOptions`, and the binding will take care of the rest
    */
    ko.bindingHandlers.multiselectOptions = {
        init: function (element, valueAccessor) {
            // add the `options` binding to the element, valueAccessor() should return an observable
            ko.applyBindingsToNode(element, {options: valueAccessor()});
        },
        update: function (element, valueAccessor) {
            // have to access the observable to get the `update` method to fire on changes
            ko.unwrap(valueAccessor());
            $(element).multiSelect('refresh');
        },
    };

    return multiselect_utils;
});
