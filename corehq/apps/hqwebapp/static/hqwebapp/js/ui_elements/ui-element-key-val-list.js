hqDefine('hqwebapp/js/ui_elements/ui-element-key-val-list', [
    'jquery',
    'underscore',
    'hqwebapp/js/main',
    'hqwebapp/js/ui_elements/ui-element-input-map',
], function (
    $,
    _,
    hqMain,
    uiInputMap
) {
    'use strict';
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
        this.$noedit_view = $('<div />');
        this.$formatted_view = $('<input type="hidden" />');
        this.$modal_trigger = $('<a class="btn btn-default enum-edit" href="#' + this.modal_id + '" ' +
            'data-toggle="modal" />').html('<i class="fa fa-pencil"></i> ' + django.gettext('Edit'));

        // Create new modal controller for this element
        var $enumModal = $('<div id="' + this.modal_id + '" class="modal fade hq-enum-modal" />');
        var $modalDialog = $('<div class="modal-dialog"/>');
        var $modalContent = $('<div class="modal-content" />');

        $modalContent.prepend('<div class="modal-header"><a class="close" data-dismiss="modal">×</a><h4 class="modal-title">'
            + this.modal_title + '</h4>' + this.sub_title + '</div>');
        var $modal_form = $('<form class="form-horizontal hq-enum-editor" action="" />'),
            $modal_body = $('<div class="modal-body" style="max-height:372px; overflow-y: scroll;" />');
        $modal_body.append($('<fieldset />'));
        $modal_body.append('<a href="#" class="btn btn-primary" data-enum-action="add"><i class="fa fa-plus"></i> ' +
            django.gettext('Add Item') + '</a>');

        $modal_form.append($modal_body);
        $modal_form.append('<div class="modal-footer"><button class="btn btn-primary" data-dismiss="modal">' +
            django.gettext('Done') + '</button></div>');
        $modalContent.append($modal_form);
        $modalDialog.append($modalContent);
        $enumModal.append($modalDialog);


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
            if (!$(this).attr('data-dismiss'))
                return false;
        });

        this.setEdit(this.edit);
    };
    KeyValList.prototype = {
        val: function (original_pairs, translated_pairs) {
            if (original_pairs === undefined) {
                return this.value;
            } else {
                var $modal_fields = $('#' + this.modal_id + ' form fieldset');
                $modal_fields.text('');
                this.$noedit_view.text('');
                this.$edit_view.html(django.gettext('Click <strong>Edit</strong> to Add Values'));

                this.value = original_pairs;
                if (translated_pairs !== undefined) {
                    this.translated_value = translated_pairs;
                }
                this.$formatted_view.val(JSON.stringify(this.value));
                if (!_.isEmpty(this.value)) {
                    this.$edit_view.text('');
                }
                let i = 0;
                for (var key in this.value) {
                    $modal_fields.append(uiInputMap.new(true, this.placeholders).val(key, this.value[key], this.translated_value[key]).ui);
                    if (this.max_display === undefined || i < this.max_display) {
                        this.$edit_view.append(uiInputMap.new(true, this.placeholders).val(key, this.value[key], this.translated_value[key]).setEdit(false).$noedit_view);
                    } else if (i === this.max_display) {
                        this.$edit_view.append('<div><strong>&hellip;</strong></div>');
                    }
                    i++;
                }
            }

        },
        setEdit: function (edit) {
            this.edit = edit;
            this.$edit_view.detach();
            this.$noedit_view.detach();
            this.$modal_trigger.detach();
            if (this.edit) {
                this.$edit_view.appendTo(this.ui);
                this.$modal_trigger.appendTo(this.ui);
                this.$formatted_view.appendTo(this.ui);
            } else {
                this.$noedit_view.appendTo(this.ui);
            }
            return this;
        },
    };

    module.new = function (guid, modalTitle, subTitle, placeholders, maxDisplay) {
        return new KeyValList(guid, modalTitle, subTitle, placeholders, maxDisplay);
    };

    return module;

});
