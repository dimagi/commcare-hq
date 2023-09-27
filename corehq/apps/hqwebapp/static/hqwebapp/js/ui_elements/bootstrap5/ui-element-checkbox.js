hqDefine('hqwebapp/js/ui_elements/bootstrap5/ui-element-checkbox', [
    'jquery',
    'hqwebapp/js/bootstrap5/main',
], function (
    $,
    hqMain
) {
    'use strict';
    var module = {};

    var Checkbox = function () {
        var that = this;
        hqMain.eventize(this);
        this.ui = $('<span/>');
        this.value = true;
        this.edit = true;

        this.$edit_view = $('<input type="checkbox"/>').change(function () {
            that.fire('change');
        });
        this.$noedit_view = $('<div class="ui-element-checkbox"/>');

        this.on('change', function () {
            this.val(this.ui.find('input').prop('checked'));
        });
        this.val(this.value);
        this.setEdit(this.edit);
    };
    Checkbox.CHECKED = "fa fa-check";
    Checkbox.UNCHECKED = "";
    Checkbox.prototype = {
        val: function (value) {
            if (value === undefined) {
                return this.value;
            } else {
                this.value = value;
                this.$edit_view.prop('checked', this.value);
                this.$noedit_view.removeClass(
                    this.value ? Checkbox.UNCHECKED : Checkbox.CHECKED
                ).addClass(
                    this.value ? Checkbox.CHECKED : Checkbox.UNCHECKED
                );
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

    module.new = function () {
        return new Checkbox();
    };

    return module;

});
