"use strict";
hqDefine('hqwebapp/js/ui_elements/bootstrap3/ui-element-key-val-list', [
    'jquery',
    'underscore',
    'hqwebapp/js/bootstrap3/main',
    'hqwebapp/js/ui_elements/bootstrap3/ui-element-input-map',
], function (
    $,
    _,
    hqMain,
    uiInputMap
) {
    var module = {};

    var KeyValList = function (guid, modalTitle, subTitle, placeholders, maxDisplay) {
        var that = this;
        hqMain.eventize(this);
        this.placeholders = placeholders;
        this.ui = $('<div class="enum-pairs" />');
        this.value = {};
        this.translated_value = {};
        this.edit = true;
        this.modal_id = 'enumModal-' + guid;
        this.modal_title = modalTitle;
        this.sub_title = subTitle ? '<p>' + subTitle + '</p>' : '';
        this.max_display = maxDisplay;

        this.$edit_view = $('<div class="well well-sm" />');
        this.$edit_view.appendTo(this.ui);

        this.$formatted_view = $('<input type="hidden" />');
        this.$formatted_view.appendTo(this.ui);

        this.$modal_trigger = $('<a class="btn btn-default enum-edit" href="#' + this.modal_id + '" ' +
            'data-toggle="modal" />').html('<i class="fa fa-pencil"></i> ' + gettext('Edit'));

        // Create new modal controller for this element
        var $enumModal = $('<div id="' + this.modal_id + '" class="modal fade hq-enum-modal" />');
        var $modalDialog = $('<div class="modal-dialog"/>');
        var $modalContent = $('<div class="modal-content" />');

        $modalContent.prepend('<div class="modal-header"><a class="close" data-dismiss="modal">×</a><h4 class="modal-title">'
            + this.modal_title + '</h4>' + this.sub_title + '</div>');
        var $modalForm = $('<form class="form-horizontal hq-enum-editor" action="" />'),
            $modalBody = $('<div class="modal-body" style="max-height:372px; overflow-y: scroll;" />');
        $modalBody.append($('<fieldset />'));
        $modalBody.append('<a href="#" class="btn btn-primary" data-enum-action="add"><i class="fa fa-plus"></i> ' +
            gettext('Add Item') + '</a>');

        $modalForm.append($modalBody);
        $modalForm.append('<div class="modal-footer"><button class="btn btn-primary" data-dismiss="modal">' +
            gettext('Done') + '</button></div>');
        $modalContent.append($modalForm);
        $modalDialog.append($modalContent);
        $enumModal.append($modalDialog);

        this.$editInstructions = $('<span>' + gettext('Click <strong>Edit</strong> to Add Values' + '</span>'));


        $('#hq-content').append($enumModal);

        $('#' + this.modal_id).on('hide.bs.modal', function () {
            var $inputMap = $(this).find('form .hq-input-map'),
                pairs = {};
            for (var i = 0; i < $inputMap.length; i++) {
                var key = $($inputMap[i]).find('.enum-key').val(),
                    mapVal = $($inputMap[i]).find('.enum-value').val();
                if (key !== undefined) {
                    pairs[key] = mapVal.toString();
                }
            }
            that.val(pairs);
            that.fire('change');
        });

        $('#' + this.modal_id + ' a').click(function () {
            if ($(this).attr('data-enum-action') === 'add') {
                $(this).parent().parent().find('fieldset').append(uiInputMap.new(true, placeholders).ui);
                $(this).parent().parent().find('fieldset input.enum-key').last().focus();
            }
            if (!$(this).attr('data-dismiss')) {
                return false;
            }
        });

        this.setEdit(this.edit);
    };
    KeyValList.prototype = {
        val: function (originalPairs, translatedPairs) {
            if (originalPairs === undefined) {
                // this function is being invoked as a getter, just return the current value
                return this.value;
            } else {
                var $modalFields = $('#' + this.modal_id + ' form fieldset');
                $modalFields.text('');

                this.value = originalPairs;
                if (translatedPairs !== undefined) {
                    this.translated_value = translatedPairs;
                }
                this.$formatted_view.val(JSON.stringify(this.value));

                this.$editInstructions.detach();
                this.$edit_view.text(''); // Clear the view to prepare for new items

                if (_.isEmpty(this.value)) {
                    if (this.edit) {
                        this.$editInstructions.appendTo(this.$edit_view);
                    }

                    return;
                }

                let i = 0;
                for (var key in this.value) {
                    $modalFields.append(uiInputMap.new(true, this.placeholders).val(key, this.value[key], this.translated_value[key]).ui);
                    if (this.max_display === undefined || i < this.max_display) {
                        let createUiInputMapView = () => uiInputMap.new(true, this.placeholders).val(key, this.value[key], this.translated_value[key]).setEdit(false).$noedit_view;
                        this.$edit_view.append(createUiInputMapView());
                    } else if (i === this.max_display) {
                        let ellipsis = '<div><strong>&hellip;</strong></div>';
                        this.$edit_view.append(ellipsis);
                    }
                    i++;
                }
            }

        },
        setEdit: function (edit) {
            if (edit) {
                this.$modal_trigger.appendTo(this.ui);
                if (this.$edit_view.text() === '') {
                    this.$editInstructions.appendTo(this.$edit_view);
                }
            } else {
                this.$modal_trigger.detach();
                this.$editInstructions.detach();
            }

            this.edit = edit;

            return this;
        },
    };

    module.new = function (guid, modalTitle, subTitle, placeholders, maxDisplay) {
        return new KeyValList(guid, modalTitle, subTitle, placeholders, maxDisplay);
    };

    return module;

});
