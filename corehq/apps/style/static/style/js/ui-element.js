/* globals $, eventize, _, django, ko */

hqDefine('style/js/ui-element.js', function () {
    'use strict';
    var module = {};

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
            var translated = module.translate_delim(value);
            this.ui.find('.lang-text').remove();
            if (translated.lang) {
                this.ui.css("position", "relative");
                var langcode_button = module.langcode_tag_btn(
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
                $(this).parent().parent().find('fieldset').append(module.input_map(true).ui);
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
                    $modal_fields.append(module.input_map(true).val(key, this.value[key], this.translated_value[key]).ui);
                    this.$edit_view.append(module.input_map(true).val(key, this.value[key], this.translated_value[key]).setEdit(false).$noedit_view);
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
                    var $langcodeButton = module.langcode_tag_btn($('<a href="#" class="btn btn-info btn-xs lang-text" />'),
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

    // To autogenerate cssid from random string
    // copied from http://stackoverflow.com/questions/7627000/javascript-convert-string-to-safe-class-name-for-css
    function makeSafeForCSS(name) {
        if (!name) {
            return "";
        }
        return name.replace(/[^a-z0-9]/g, function(s) {
            var c = s.charCodeAt(0);
            if (c === 32) return '-';
            if (c >= 65 && c <= 90) return '_' + s.toLowerCase();
            return '__' + ('000' + c.toString(16)).slice(-4);
        });
    }

    /**
    * MapItem is a ko representation for `item` objects.
    *
    * @param item: a raw object which contains keys called `key` and `value`.
    *              the `value` in a item itself is an object, a mapping
    *              of language codes to strings
    * @param mappingContext: an object which has context of current UI language and whether
    *                 `value` of MapItem is a file-path to an icon or a simple string
    */
    var MapItem = function(item, index, mappingContext){
        var self = this;
        this.key = ko.observable(item.key);
        this.editing = ko.observable(false);

        this.cssId = ko.computed(function(){
            return makeSafeForCSS(this.key()) || '_blank_';
        }, this);


        // util function to generate icon-name of the format "module<module_id>_list_icon_<property_name>_<hash_of_item.key>"
        this.generateIconPath = function(){
            var randomFourDigits = Math.floor(Math.random()*9000) + 1000;
            var iconPrefix =  "jr://file/commcare/image/module" + mappingContext.module_id + "_list_icon_" + mappingContext.property_name.val() + "_";
            return iconPrefix + randomFourDigits + ".png";
        };


        var app_manager = hqImport('app_manager/js/app_manager_media.js');
        var uploaders = hqImport("app_manager/js/nav_menu_media_common.js");
        // attach a media-manager if item.value is a file-path to icon
        if (mappingContext.values_are_icons()) {
            var actualPath = item.value[mappingContext.lang];
            var defaultIconPath = actualPath || self.generateIconPath();
            this.iconManager = new app_manager.AppMenuMediaManager({
                ref: {
                    "path": actualPath,
                    "icon_type": "icon-picture",
                    "media_type": "Image",
                    "media_class": "CommCareImage",
                    "icon_class": "icon-picture",
                },
                objectMap: mappingContext.multimedia,
                uploadController: uploaders.iconUploader,
                defaultPath: defaultIconPath,
                inputElement: $("#" + self.cssId()),
            });
        };

        this.toggleEditMode = function() {
            this.editing(!this.editing());
        };

        this.value = ko.computed(function() {
            // ko.observable for item.value
            var new_value = [];
            var langs = _.union(_(item.value).keys(), [mappingContext.lang]) ;
            _.each(langs, function(lang){
                // return ko reference to path in `iconManager` for current UI language value
                if (mappingContext.values_are_icons() && lang === mappingContext.lang){
                    new_value.push([lang, self.iconManager.customPath]);
                }
                // return new ko.observable for other languages
                else{
                    new_value.push([lang, ko.observable(item.value[lang])]);
                }
            });
            return _.object(new_value);
        }, this);

        this.key.subscribe(function(newValue) {
            if(mappingContext.duplicatedItems.indexOf(newValue) === -1 && mappingContext._isItemDuplicated(newValue)) {
                mappingContext.duplicatedItems.push(newValue);
            }

        });

        this.key.subscribe(function(oldValue) {
            var index = mappingContext.duplicatedItems.indexOf(oldValue);
            if(index !== -1 && !mappingContext._isItemDuplicated(oldValue, 2)) {
                mappingContext.duplicatedItems.remove(oldValue);
            }
        }, null, "beforeChange");
    };

    /**
     * A MapList is an ordered list MapItem objects
     */
    function MapList(o) {
        var self = this;
        self.lang = o.lang;
        self.langs = [o.lang].concat(o.langs);
        self.module_id = o.module_id;
        self.items = ko.observableArray();
        self.duplicatedItems = ko.observableArray();
        self.values_are_icons = ko.observable(o.values_are_icons || false);
        self.values_are_conditions = ko.observable(o.values_are_conditions || false);
        self.multimedia = o.multimedia;
        self.property_name = o.property_name;

        self.labels = ko.computed(function() {
            if (this.values_are_icons()) {
                return {
                    placeholder: django.gettext('Calculation'),
                    duplicated: django.gettext('Calculation is duplicated'),
                    addButton: django.gettext('Add Image'),
                };
            }
            else if (this.values_are_conditions()) {
                return {
                    placeholder: django.gettext('Calculation'),
                    duplicated: django.gettext('Calculation is duplicated'),
                    addButton: django.gettext('Add Key, Value Mapping'),
                };
            }
            else {
                return {
                    placeholder: django.gettext('Key'),
                    duplicated: django.gettext('Key is duplicated'),
                    addButton: django.gettext('Add Key, Value Mapping'),
                };
            }
        }, this);

        self.setItems = function (items) {
            self.items(_(items).map(function (item, i) {
                return new MapItem(item, i, self);
            }));
        };
        self.setItems(o.items);

        self.backup = function (value) {
            var backup;
            for (var i = 0; i < self.langs.length; i += 1) {
                var lang = self.langs[i];
                backup = value[lang];
                if (backup && backup() !== '') {
                    return {lang: lang, value: backup()};
                }
            }
            return {lang: null, value: 'value'};
        };
        self.removeItem = function (item) {
            self.items.remove(item);
            if(!self._isItemDuplicated(ko.utils.unwrapObservable(item.key)))
                self.duplicatedItems.remove(ko.utils.unwrapObservable(item.key));
        };
        self.addItem = function () {
            var raw_item = {key: '', value: {}};
            raw_item.value[self.lang] = '';

            var item = new MapItem(raw_item, self.items.length, self);
            self.items.push(item);
            if(self.duplicatedItems.indexOf('') === -1 && self._isItemDuplicated('')) {
                self.duplicatedItems.push('');
            }
        };

        self._isItemDuplicated = function(key, max_counts) {
            if(typeof(max_counts) === 'undefined') max_counts = 1;
            var items = self.getItems();
            var counter = 0;
            for(var i = 0; i < items.length; i++) {
                var item = items[i];
                if(ko.utils.unwrapObservable(item.key) === key) {
                    counter++;
                    if(counter > max_counts) return true;
                }
            }
            return false;
        };

        self.isItemDuplicated = function(key) {
            return self.duplicatedItems.indexOf(key) !== -1;
        };

        self.getItems = function () {
            return _(self.items()).map(function (item) {
                return {
                    key: ko.utils.unwrapObservable(item.key),
                    value: _.object(_(item.value()).map(function (value, lang) {
                        return [lang, ko.utils.unwrapObservable(value)];
                    }))
                };
            });

        };
    }

    module.input = function (value) {
        return new Input($('<input type="text" class="form-control"/>'), value, function ($elem) {
            return $elem.val();
        }, function ($elem, value) {
            return $elem.val(value);
        }, function ($elem, value){
            return $elem.attr('placeholder', value);
        });
    };

    module.textarea = function () {
        return new Input($('<textarea class="form-control"/>'), function ($elem) {
            return $elem.val();
        }, function ($elem, value) {
            return $elem.val($elem, value);
        }, function ($elem, value){
            $elem.attr('placeholder', value);
        });
    };

    module.select = function (options) {
        return new Select(options);
    };

    module.map_list = function(guid, modalTitle) {
        return new KeyValList(guid, modalTitle);
    };

    module.input_map = function(show_del_button) {
        return new InputMap(show_del_button);
    };

    module.checkbox = function () {
        return new Checkbox();
    };

    module.serialize = function (obj) {
        var cpy;
        if (typeof obj.val === 'function') {
            return obj.val();
        } else if (_.isArray(obj)) {
            return _.map(obj, module.serialize);
        } else if (_.isObject(obj)) {
            cpy = _.clone(obj);
            _.chain(cpy).map(function (value, key) {
                cpy[key] = module.serialize(value);
            });
            return cpy;
        } else {
            return obj;
        }
    };

    module.LANG_DELIN = "{{[[*LANG*]]}}";

    module.langcode_tag_btn = function ($elem, new_lang) {
        return new LangCodeButton($elem, new_lang);
    };

    module.translate_delim = function (value) {
        var values = value.split(module.LANG_DELIN);
        return {
            value: values[0],
            lang: (values.length > 1 ? values[1] : null),
        };
    };

    module.key_value_mapping = function (o) {
        var m = new MapList(o);
        m.edit = ko.observable(true);
        m.buttonText = o.buttonText || "Edit",
        m.values_are_icons = ko.observable(o.values_are_icons || false);
        m.values_are_conditions = ko.observable(o.values_are_conditions || false);
        m.openModal = function () {
            // create a throw-away modal every time
            // lets us create a sandbox for editing that you can cancel
            var $modalDiv = $(document.createElement("div"));
            $modalDiv.attr("data-bind", "template: 'key_value_mapping_modal'");
            var copy = new MapList({
                lang: o.lang,
                langs: o.langs,
                module_id: o.module_id,
                items: m.getItems(),
                values_are_icons: m.values_are_icons(),
                values_are_conditions: m.values_are_conditions(),
                multimedia: m.multimedia,
                property_name: o.property_name,
            });
            $modalDiv.koApplyBindings({
                modalTitle: ko.computed(function() {
                    return 'Edit Mapping for ' + this.property_name.val();
                }, this),
                mapList: copy,
                save: function (data, e) {
                    if(copy.duplicatedItems().length > 0) {
                        e.stopImmediatePropagation();
                    } else {
                        m.setItems(copy.getItems());
                    }
                }
            });

            var $modal = $modalDiv.find('.modal');
            $modal.appendTo('body');
            $modal.modal({
                show: true,
                backdrop: 'static',
            });
            $modal.on('hidden', function () {
                $modal.remove();
            });
        };
        m.setEdit = function (edit) {
            m.edit(edit);
        };
        var $div = $(document.createElement("div"));
        $div.attr("data-bind", "template: \'key_value_mapping_template\'");
        $div.koApplyBindings(m);
        m.ui = $div;
        eventize(m);
        m.items.subscribe(function () {
            m.fire('change');
        });
        return m;
    };


    return module;

});
