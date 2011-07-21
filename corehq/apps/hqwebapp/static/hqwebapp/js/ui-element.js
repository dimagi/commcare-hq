/*globals $ */
var eventize, uiElement;
(function () {
    'use strict';
    eventize = function (that) {
        var events = {};
        that.on = function (tag, callback) {
            if (events[tag] === undefined) {
                events[tag] = [];
            }
            events[tag].push(callback);
            return that;
        };
        that.fire = function (tag, e) {
            var i;
            if (events[tag] !== undefined) {
                for (i = 0; i < events[tag].length; i += 1) {
                    events[tag][i].apply(that, [e]);
                }
            }
            return that;
        };
    };

    uiElement = {
        input: (function () {
            var Input = function () {
                var that = this;
                eventize(this);
                this.ui = $('<span/>');
                this.value = "";
                this.edit = true;

                this.$edit_view = $('<input type="text"/>').change(function () {
                    that.fire('change');
                });
                this.$noedit_view = $('<span class="ui-element-input"/>');

                this.on('change', function () {
                    this.val(this.ui.find('input').val());
                });
                this.setEdit(this.edit);
            };
            Input.prototype = {
                val: function (value) {
                    if (value === undefined) {
                        return this.value;
                    } else {
                        this.value = value;
                        this.$edit_view.val(this.value);
                        this.$noedit_view.text(this.value);
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
                }
            };
            return function () {
                return new Input();
            };
        }()),
        select: (function () {
            var Select = function (options) {
                var that = this,
                    i,
                    option;
                eventize(this);
                this.ui = $('<span/>');
                this.value = "";
                this.edit = true;
                this.options = options;

                this.on('change', function () {
                    this.val(this.ui.find('select').val());
                });

                this.$edit_view = $('<select/>').change(function () {
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
                        this.$edit_view.val(this.value);
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
                }
            };
            return function (options) {
                return new Select(options);
            };
        }()),
        checkbox: (function () {
            var Checkbox = function () {
                var that = this;
                eventize(this);
                this.ui = $('<span/>');
                this.value = true;
                this.edit = true;

                this.$edit_view = $('<input type="checkbox"/>').change(function () {
                    that.fire('change');
                });
                this.$noedit_view = $('<div class="ui-element-checkbox ui-icon"/>');

                this.on('change', function () {
                    this.val(this.ui.find('input').prop('checked'));
                });
                this.val(this.value);
                this.setEdit(this.edit);
            };
            Checkbox.CHECKED = "ui-icon-check";
            Checkbox.UNCHECKED = "ui-icon-close";
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
                }
            };
            return function () {
                return new Checkbox();
            };
        }())
    };
}());