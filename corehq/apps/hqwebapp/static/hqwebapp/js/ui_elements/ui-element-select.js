/* globals hqDefine, hqImport, $ */

hqDefine('hqwebapp/js/ui_elements/ui-element-select', function () {
    'use strict';
    var module = {};

    var Select = function (options) {
        var that = this,
            i,
            option;
        hqImport("hqwebapp/js/main").eventize(this);
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

        this.setOptions(options || []);

        this.$noedit_view = $('<span class="ui-element-select"/>');

        this.setEdit(this.edit);
    };

    Select.prototype = {
        val: function (value) {
            if (!_.isString(value)) {
                return this.value;
            } else {
                this.value = value;
                var option = _.find(this.options, function (o) { return value === o.value; }) || {},
                    label = option.label;
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
        setIcon: function (icon) {
            this.icon = icon;
            if (icon) {
                $('<i> </i>').addClass(icon).prependTo(this.$noedit_view);
            }
            return this;
        },
        setOptions: function (options) {
            this.options = options;
            this.$edit_view.html('');
            for (var i = 0; i < this.options.length; i += 1) {
                var option = this.options[i],
                    label = option.label === undefined ? option : option.label,
                    value = option.value === undefined ? option : option.value;
                $('<option/>').text(label).val(value).appendTo(this.$edit_view);
            }
        },
    };

    module.new = function (options) {
        return new Select(options);
    };

    return module;

});
