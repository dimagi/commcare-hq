/* global django:false _:false */

hqDefine('style/js/components/multiselect_utils', function () {
    var multiselect_utils = {};

    var _renderHeader = function (title, action, search) {
        var header = _.template('<div class="ms-header"><%= headerTitle %><%= actionButton %></div><%= searchInput %>');
        return header({
            headerTitle: title,
            actionButton: action || '',
            searchInput: search || '',
        });
    };

    var _renderAction = function (buttonId, buttonClass, buttonIcon, text) {
        var action = _.template(
            '<a href="#" class="btn <%=actionButtonClass %> btn-xs pull-right" id="<%= actionButtonId %>">' +
                '<i class="<%= actionButtonIcon %>"></i> <%= actionButtonText %>' +
            '</a>'
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
                '<input type="search" class="form-control search-input" id="<%= searchInputId %>" autocomplete="off" placeholder="<%= searchInputPlaceholder %>" />' +
            '</div>'
        );
        return input({
            searchInputId: inputId,
            searchInputPlaceholder: placeholder,
        });
    };

    multiselect_utils.createFullMultiselectWidget = function (
        multiselectId,
        selectableHeaderTitle,
        selectedHeaderTitle,
        searchItemTitle
    ) {
        var selectAllId = multiselectId + '-select-all',
            removeAllId = multiselectId + '-remove-all',
            searchSelectableId = multiselectId + '-search-selectable',
            searchSelectedId = multiselectId + '-search-selected';

        $('#' + multiselectId).multiSelect({
            selectableHeader: _renderHeader(
                selectableHeaderTitle,
                _renderAction(selectAllId, 'btn-info', 'fa fa-plus', django.gettext("Add All")),
                _renderSearch(searchSelectableId, searchItemTitle)
            ),
            selectionHeader: _renderHeader(
                selectedHeaderTitle,
                _renderAction(removeAllId, 'btn-default', 'fa fa-remove', django.gettext("Remove All")),
                _renderSearch(searchSelectedId, searchItemTitle)
            ),
            afterInit: function () {
                var that = this,
                    $selectableSearch = $('#'+searchSelectableId),
                    $selectionSearch = $('#'+searchSelectedId),
                    selectableSearchString = '#'+that.$container.attr('id')+' .ms-elem-selectable:not(.ms-selected)',
                    selectionSearchString = '#'+that.$container.attr('id')+' .ms-elem-selection.ms-selected';

                that.qs1 = $selectableSearch.quicksearch(selectableSearchString)
                .on('keydown', function (e) {
                    if (e.which === 40) {
                        that.$selectableUl.focus();
                        return false;
                    }
                })
                .on('keyup change search input', function () {
                    // disable add all functionality so that user is not confused
                    if (that.qs1.val().length > 0) {
                        $('#' + selectAllId).addClass('disabled').prop('disabled', true);
                    } else {
                        $('#' + selectAllId).removeClass('disabled').removeProp('disabled');
                    }
                });

                that.qs2 = $selectionSearch.quicksearch(selectionSearchString)
                .on('keydown', function (e) {
                    if (e.which === 40) {
                        that.$selectionUl.focus();
                        return false;
                    }
                })
                .on('keyup change search input', function () {
                    // disable remove all functionality so that user is not confused
                    if (that.qs2.val().length > 0) {
                        $('#' + removeAllId).addClass('disabled').prop('disabled', true);
                    } else {
                        $('#' + removeAllId).removeClass('disabled').removeProp('disabled');
                    }
                });
            },
            afterSelect: function(){
                this.qs1.cache();
                // remove search option so that user doesn't get confused
                this.qs2.val('').search('');
                $('#' + removeAllId).removeClass('disabled').removeProp('disabled');
                this.qs2.cache();
            },
            afterDeselect: function(){
                // remove search option so that user doesn't get confused
                this.qs1.val('').search('');
                $('#' + selectAllId).removeClass('disabled').removeProp('disabled');
                this.qs1.cache();
                this.qs2.cache();
            },
        });

        $('#' + selectAllId).click(function () {
            $('#' + multiselectId).multiSelect('select_all');
            return false;
        });
        $('#' + removeAllId).click(function () {
            $('#' + multiselectId).multiSelect('deselect_all');
            return false;
        });
    };

    return multiselect_utils;
});
