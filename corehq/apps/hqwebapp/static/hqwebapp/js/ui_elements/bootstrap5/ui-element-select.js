'use strict';
hqDefine('hqwebapp/js/ui_elements/bootstrap5/ui-element-select', [
    'jquery',
    'underscore',
    'hqwebapp/js/bootstrap5/main',
], function (
    $,
    _,
    hqMain
) {
    var module = {};

    var Select = function (options) {
        var that = this;
        hqMain.eventize(this);
        this.ui = $('<span/>');
        this.value = "";
        this.valueLabel = "";
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
                let option = _.find(this.options, o => value === o.value);
                if (!option) {
                    // add a new option
                    option = {value: value, label: value};
                    this.options.push(option);
                    if (!this.$edit_view.find(`option[value='${value}']`).length) {
                        // this is needed to preserve the option after changing the list of properties
                        $('<option/>').text(option.label).val(option.value).appendTo(this.$edit_view);
                    }
                }
                this.value = option.value;
                this.valueLabel = option.label;
                this.$edit_view.val(String(this.value || ''));
                this.$noedit_view.text(option.label);
                return this;
            }
        },
        valLabel: function () {
            return this.valueLabel;
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
                if ('groupName' in option) {
                    $(`<optgroup label="${option.groupName}"/>`).appendTo(this.$edit_view);
                } else {
                    $('<option/>').text(option.label).val(option.value).appendTo(this.$edit_view);
                }
            }
        },
    };

    module.new = function (options) {
        return new Select(options);
    };

    return module;

});
