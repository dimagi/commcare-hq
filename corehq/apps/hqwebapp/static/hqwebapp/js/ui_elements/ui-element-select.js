hqDefine('hqwebapp/js/ui_elements/ui-element-select', [
    'jquery',
    'hqwebapp/js/main',
], function (
    $,
    hqMain
) {
    'use strict';
    var module = {};

    var Select = function (options) {
        var that = this,
            i,
            option;
        hqMain.eventize(this);
        this.ui = $('<span/>');
        this.value = "";
        this.edit = true;
        this.options = options;

        this.on('change', function () {
            this.val(this.ui.find('select').val());
        });

        this.$edit_view = $('<select class="form-control"/>').change(function () {
            that.fire('change');
        });
        for (i = 0; i < this.options.length; i += 1) {
            option = this.options[i];
            $('<option/>').text(option.label).val(option.value).appendTo(this.$edit_view);
        }

        this.$noedit_view = $('<span class="ui-element-select"/>');

        this.setEdit(this.edit);
    };

    Select.prototype = {
        val: function (value) {
            var i, option, label;
            if (value === undefined) {
                return this.value;
            } else {
                this.value = value;
                for (i = 0; i < this.options.length; i += 1) {
                    option = this.options[i];
                    if (option.value === value) {
                        label = option.label;
                        break;
                    }
                }
                this.$edit_view.val(String(this.value || ''));
                this.$noedit_view.text(label);
                return this;
            }
        },
        setEdit: function (edit) {
            this.edit = edit;
            this.$edit_view.detach();
            this.$noedit_view.detach();
            if (this.edit) {
                this.$edit_view.appendTo(this.ui);
            } else {
                this.$noedit_view.appendTo(this.ui);
            }
            return this;
        },
    };

    module.new = function (options) {
        return new Select(options);
    };

    return module;

});
