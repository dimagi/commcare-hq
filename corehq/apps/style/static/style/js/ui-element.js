/*globals $, eventize, _, django */

var langcodeTag;

(function () {
    'use strict';

    langcodeTag = {
        LANG_DELIN: "{{[[*LANG*]]}}",
        button_tag: (function () {
            var LangCodeButton = function ($elem, new_lang) {
                this.button = $elem;
                this.button.click(function () {
                    return false;
                });
                this.lang_code = new_lang;
                this.lang(new_lang);
            };
            LangCodeButton.prototype = {
                lang: function (value) {
                    if (value === undefined) {
                        return this.lang_code;
                    } else {
                        this.lang_code = value;
                        this.button.text(this.lang_code);
                    }
                },
            };
            return function ($elem, new_lang) {
                return new LangCodeButton($elem, new_lang);
            };
        }()),
        translate_delim: function (value) {
            var values = value.split(langcodeTag.LANG_DELIN);
            return {
                value: values[0],
                lang: (values.length > 1 ? values[1] : null),
            };
        },
    };

}());

var uiElement;
(function () {
    'use strict';

    var Input = function ($elem, initialValue, getElemValue, setElemValue, setPlaceholderValue) {
        var that = this;
        eventize(this);
        this.ui = $('<div class="app-designer-input"/>');
        this.value = "";
        this.edit = true;
        this.getElemValue = function () {
            return getElemValue($elem);
        };
        this.setElemValue = function (value) {
            setElemValue($elem, value);
        };
        this.setPlaceholderValue = function (value) {
            setPlaceholderValue($elem, value);
        };

        this.$edit_view = $elem.on('change textchange', function () {
            that.fire('change');
        });
        this.$noedit_view = $('<span class="ui-element-input"/>');

        this.on('change', function () {
            this.value = this.getElemValue();
            this.$noedit_view.text(this.value);
        });
        this.setEdit(this.edit);
        this.val(initialValue);

        // Trigger the textchange plugin's logic, so that it gets the correct initialValue set
        $elem.trigger('keyup');
    };
    Input.prototype = {
        val: function (value) {
            if (value === undefined) {
                return this.value;
            } else {
                this.value = value;
                this.setVisibleValue(this.value);
                return this;
            }
        },
        setVisibleValue: function (value) {
            var translated = langcodeTag.translate_delim(value);
            this.ui.find('.lang-text').remove();
            if (translated.lang) {
                this.ui.css("position", "relative");
                var langcode_button = langcodeTag.button_tag(
                    $('<a href="#" class="btn btn-info btn-xs lang-text" style="position: absolute; top: 6px; right: 6px;" />'),
                    translated.lang);
                this.ui.append(langcode_button.button);
                this.setPlaceholderValue(translated.value);
                this.$edit_view.change(function () {
                    if ($(this).val() === "")
                        langcode_button.button.show();
                    else
                        langcode_button.button.hide();
                });
            } else
                this.setElemValue(translated.value);
            this.$noedit_view.text(translated.value);
            this.setIcon(this.icon);
            return this;
        },
        setHtml: function (value) {
            this.$noedit_view.html(value);
            this.setIcon(this.icon);
            return this;
        },
        setIcon: function (icon) {
            this.icon = icon;
            if (icon) {
                $('<i> </i>').addClass(icon).prependTo(this.$noedit_view);
            }
            return this;
        },
        setEdit: function (edit) {
            this.edit = edit;
            this.$edit_view.detach();
            this.$noedit_view.detach();
            if (this.edit) {
                this.$edit_view.prependTo(this.ui);
            } else {
                this.$noedit_view.prependTo(this.ui);
            }
            return this;
        },
    };

    uiElement = {
        input: function (value) {
            return new Input($('<input type="text" class="form-control"/>'), value, function ($elem) {
                return $elem.val();
            }, function ($elem, value) {
                return $elem.val(value);
            }, function ($elem, value){
                return $elem.attr('placeholder', value);
            });
        },
        textarea: function () {
            return new Input($('<textarea class="form-control"/>'), function ($elem) {
                return $elem.val();
            }, function ($elem, value) {
                return $elem.val($elem, value);
            }, function ($elem, value){
                $elem.attr('placeholder', value);
            });
        },
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
            return function (options) {
                return new Select(options);
            };
        }()),
        map_list: (function() {
            var KeyValList = function(guid, modal_title) {
                var that = this;
                eventize(this);
                this.ui = $('<div class="enum-pairs" />');
                this.value = {};
                this.translated_value = {};
                this.edit = true;
                this.modal_id = 'enumModal-'+guid;
                this.modal_title = modal_title;

                this.$edit_view = $('<div class="well well-sm" />');
                this.$noedit_view = $('<div />');
                this.$formatted_view = $('<input type="hidden" />');
                this.$modal_trigger = $('<a class="btn btn-default enum-edit" href="#'+this.modal_id+'" ' +
                    'data-toggle="modal" />').html('<i class="fa fa-pencil"></i> ' + django.gettext('Edit'));

                // Create new modal controller for this element
                var $enumModal = $('<div id="'+this.modal_id+'" class="modal fade hq-enum-modal" />');
                var $modalDialog = $('<div class="modal-dialog"/>');
                var $modalContent = $('<div class="modal-content" />');

                $modalContent.prepend('<div class="modal-header"><a class="close" data-dismiss="modal">×</a><h4 class="modal-title">'
                    + django.gettext('Edit Mapping for ') + this.modal_title + '</h4></div>');
                var $modal_form = $('<form class="form-horizontal hq-enum-editor" action="" />'),
                    $modal_body = $('<div class="modal-body" style="max-height:372px; overflow-y: scroll;" />');
                $modal_body.append($('<fieldset />'));
                $modal_body.append('<a href="#" class="btn btn-success" data-enum-action="add"><i class="fa fa-plus"></i> ' +
                    django.gettext('Add Key &rarr; Value Mapping') + '</a>');

                $modal_form.append($modal_body);
                $modal_form.append('<div class="modal-footer"><button class="btn btn-primary" data-dismiss="modal">' +
                    django.gettext('Done') + '</button></div>');
                $modalContent.append($modal_form);
                $modalDialog.append($modalContent);
                $enumModal.append($modalDialog);


                $('#hq-modal-home').append($enumModal);

                $('#'+this.modal_id).on('hide.bs.modal', function() {
                    var $inputMap = $(this).find('form .hq-input-map'),
                        pairs = {};
                    for (var i=0; i < $inputMap.length; i++) {
                        var key = $($inputMap[i]).find('.enum-key').val(),
                            mapVal = $($inputMap[i]).find('.enum-value').val();
                        if (key !== undefined){
                            pairs[key] = mapVal.toString();
                        }
                    }
                    that.val(pairs);
                    that.fire('change');
                });

                $('#'+this.modal_id+' a').click(function() {
                    if($(this).attr('data-enum-action') === 'add') {
                        $(this).parent().parent().find('fieldset').append(uiElement.input_map(true).ui);
                        $(this).parent().parent().find('fieldset input.enum-key').last().focus();
                    }
                    if (!$(this).attr('data-dismiss'))
                        return false;
                });

                this.setEdit(this.edit);
            };
            KeyValList.prototype = {
                val: function(original_pairs, translated_pairs) {
                    if (original_pairs === undefined) {
                        return this.value;
                    } else {
                        var $modal_fields = $('#'+this.modal_id+' form fieldset');
                        $modal_fields.text('');
                        this.$noedit_view.text('');
                        this.$edit_view.html(django.gettext('Click <strong>Edit</strong> below to add mappings'));

                        this.value = original_pairs;
                        if (translated_pairs !== undefined) {
                            this.translated_value = translated_pairs;
                        }
                        this.$formatted_view.val(JSON.stringify(this.value));
                        if (!_.isEmpty(this.value)) {
                            this.$edit_view.text('');
                        }
                        for (var key in this.value) {
                            $modal_fields.append(uiElement.input_map(true).val(key, this.value[key], this.translated_value[key]).ui);
                            this.$edit_view.append(uiElement.input_map(true).val(key, this.value[key], this.translated_value[key]).setEdit(false).$noedit_view);
                        }
                    }

                },
                setEdit: function(edit) {
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
            return function (guid, modal_title) {
                return new KeyValList(guid, modal_title);
            };
        }()),
        input_map: (function() {
            var InputMap = function (show_del_button) {
                var that = this;
                eventize(this);
                this.ui = $('<div class="form-group hq-input-map" />');
                this.value = {
                    key: "",
                    val: "",
                };
                this.edit = true;
                this.show_delete = show_del_button;
                this.on('change', function() {
                    this.val(this.ui.find(".enum-key").val(), this.ui.find(".enum-value").val());
                });
                this.on('remove', function() {
                    this.ui.remove();
                });

                this.$edit_view = $('<div class="form-inline" style="margin-left:5px;" />');
                var key_input = $('<input type="text" class="form-control enum-key" style="width:220px;" placeholder="' + django.gettext('key') + '" />'),
                    val_input = $('<input type="text" class="form-control enum-value" style="width:220px;" placeholder="' + django.gettext('value') + '" />');
                key_input.change(function () {
                    that.fire('change');
                });
                val_input.change(function() {
                    that.fire('change');
                });
                this.$edit_view.append(key_input);
                this.$edit_view.append(' <i class="fa fa-arrow-right"></i> ');
                this.$edit_view.append(val_input);
                if(this.show_delete) {
                    var $deleteButton = $('<a href="#" data-enum-action="remove" class="btn btn-danger" />');
                    $deleteButton.append('<i class="fa fa-remove"></i> ' + django.gettext('Delete'));
                    $deleteButton.click(function() {
                        that.fire('remove');
                        return false;
                    });
                    this.$edit_view.append(' ');
                    this.$edit_view.append($deleteButton);
                }
                this.$noedit_view = $('<div />');

                this.setEdit(this.edit);
            };
            InputMap.prototype = {
                val: function(map_key, map_val, translated_map_val) {
                    if (map_key === undefined) {
                        return this.value;
                    } else {
                        this.value = {
                            key: map_key,
                            val: map_val,
                        };
                        this.$edit_view.find(".enum-key").val(map_key);
                        this.$edit_view.find(".enum-value").val(map_val);
                        if (map_val === "" && translated_map_val !== undefined && translated_map_val !== "") {
                            this.$edit_view.find(".enum-value").attr("placeholder", translated_map_val.value);
                            var $langcodeButton = langcodeTag.button_tag($('<a href="#" class="btn btn-info btn-xs lang-text" />'),
                                translated_map_val.lang);
                            $langcodeButton.button.attr("style", "position: absolute; top: 6px; right: 6px;");
                            this.$edit_view.find(".enum-value").css("position", "relative").after($langcodeButton.button);
                            this.on('change', function () {
                                if (this.$edit_view.find(".enum-value").val() === "")
                                    $langcodeButton.button.show();
                                else
                                    $langcodeButton.button.hide();
                            });

                        }
                        if(map_key) {
                            this.$noedit_view.html('<strong>' + map_key + '</strong> &rarr; ' + (
                                map_val ? map_val : '<i class="fa fa-remove"></i>'
                            ));
                        }else{
                            this.$noedit_view.text("");
                        }
                        return this;
                    }
                },
                setEdit: function(edit) {
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
            return function (show_del_button) {
                return new InputMap(show_del_button);
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
            return function () {
                return new Checkbox();
            };
        }()),
        serialize: function (obj) {
            var cpy;
            if (typeof obj.val === 'function') {
                return obj.val();
            } else if (_.isArray(obj)) {
                return _.map(obj, uiElement.serialize);
            } else if (_.isObject(obj)) {
                cpy = _.clone(obj);
                _.chain(cpy).map(function (value, key) {
                    cpy[key] = uiElement.serialize(value);
                });
                return cpy;
            } else {
                return obj;
            }
        },
    };
}());
