hqDefine('style/js/components/multiselect_utils', function () {
    var multiselect_utils = {};

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
            selectableHeader: '<div class="ms-header">' + selectableHeaderTitle +
                                    '<a href="#" class="btn btn-info btn-xs pull-right" id="' + selectAllId + '">' +
                                    '<i class="fa fa-plus"></i> ' + django.gettext("Add All") +
                               '</a></div>' +
                               '<div class="input-group ms-input-group">' +
                                    '<span class="input-group-addon"><i class="fa fa-search"></i></span>' +
                                    '<input type="search" class="form-control search-input" id="' + searchSelectableId + '" autocomplete="off" placeholder="' + searchItemTitle + '" />' +
                               '</div>',
            selectionHeader:   '<div class="ms-header">' + selectedHeaderTitle +
                                    '<a href="#" class="btn btn-default btn-xs pull-right" id="' + removeAllId + '">' +
                                    '<i class="fa fa-remove"></i> ' + django.gettext("Remove All") +
                               '</a></div>' +
                               '<div class="input-group ms-input-group">' +
                                    '<span class="input-group-addon"><i class="fa fa-search"></i></span>' +
                                    '<input type="search" class="form-control search-input" id="' + searchSelectedId + '" autocomplete="off" placeholder="' + searchItemTitle + '" />' +
                               '</div>',
            afterInit: function(ms){
                var that = this,
                    $selectableSearch = $('#'+searchSelectableId),
                    $selectionSearch = $('#'+searchSelectedId),
                    selectableSearchString = '#'+that.$container.attr('id')+' .ms-elem-selectable:not(.ms-selected)',
                    selectionSearchString = '#'+that.$container.attr('id')+' .ms-elem-selection.ms-selected';

                that.qs1 = $selectableSearch.quicksearch(selectableSearchString)
                .on('keydown', function(e){
                  if (e.which === 40){
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
                .on('keydown', function(e){
                  if (e.which == 40){
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
            }
        });

        $('#' + selectAllId).click(function(e){
            $('#' + multiselectId).multiSelect('select_all');
            return false;
        });
        $('#' + removeAllId).click(function(e){
            $('#' + multiselectId).multiSelect('deselect_all');
            return false;
        });
    };

    return multiselect_utils;
});
