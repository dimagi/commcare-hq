hqDefine('hqwebapp/js/ui_elements/ui-element-select', [
    'jquery',
    'underscore',
    'hqwebapp/js/main',
], function (
    $,
    _,
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
        this.options = [];

        this.on('change', function () {
            this.val(this.ui.find('select').val());
        });

        this.$edit_view = $('<select class="form-control"/>').change(function () {
            that.fire('change');
        });

        this.$noedit_view = $('<span class="ui-element-select"/>');

        this.setOptions(options || []);

        this.setEdit(this.edit);
    };

    Select.prototype = {
        val: function (value) {
            if (!_.isString(value)) {
                return this.value;
            } else {
                const option = _.find(this.options, o => value === o.value) || {};
                this.value = option.value;
                this.$edit_view.val(String(this.value || ''));
                this.$noedit_view.text(option.label);
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
        setIcon: function (icon) {
            this.icon = icon;
            if (icon) {
                $('<i> </i>').addClass(icon).prependTo(this.$noedit_view);
            }
            return this;
        },
        setOptions: function (options) {
            this.options = options.map(o => _.isString(o) ? {value: o, label: o} : o);
            this.$edit_view.html('');
            for (var i = 0; i < this.options.length; i += 1) {
                var option = this.options[i];
                $('<option/>').text(option.label).val(option.value).appendTo(this.$edit_view);
            }
            // preserve selection if possible
            this.val(this.value);
        },
    };

    module.new = function (options) {
        return new Select(options);
    };

    return module;

});
