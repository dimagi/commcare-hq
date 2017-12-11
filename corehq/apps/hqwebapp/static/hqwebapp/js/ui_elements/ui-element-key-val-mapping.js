/* globals hqDefine, hqImport, $, _, django, ko */

hqDefine('hqwebapp/js/ui_elements/ui-element-key-val-mapping', function () {
    'use strict';
    var module = {};

    // To autogenerate cssid from random string
    // copied from http://stackoverflow.com/questions/7627000/javascript-convert-string-to-safe-class-name-for-css
    var makeSafeForCSS = function(name) {
        if (!name) {
            return "";
        }
        return name.replace(/[^a-z0-9]/g, function(s) {
            var c = s.charCodeAt(0);
            if (c === 32) return '-';
            if (c >= 65 && c <= 90) return '_' + s.toLowerCase();
            return '__' + ('000' + c.toString(16)).slice(-4);
        });
    };

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


        var app_manager = hqImport('app_manager/js/app_manager_media');
        var uploaders = hqImport("app_manager/js/nav_menu_media_common");
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
        }

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
    var MapList = function(o) {
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
                    badXML: django.gettext('Calculation contains an invalid character.'),
                };
            }
            else if (this.values_are_conditions()) {
                return {
                    placeholder: django.gettext('Calculation'),
                    duplicated: django.gettext('Calculation is duplicated'),
                    addButton: django.gettext('Add Key, Value Mapping'),
                    badXML: django.gettext('Calculation contains an invalid character.'),
                };
            }
            else {
                return {
                    placeholder: django.gettext('Key'),
                    duplicated: django.gettext('Key is duplicated'),
                    addButton: django.gettext('Add Key, Value Mapping'),
                    badXML: django.gettext('Key contains an invalid character.'),
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

        self.hasBadXML = function(key) {
            if (self.values_are_icons() || self.values_are_conditions()) {
                // Expressions can contain whatever
                return false;
            }

            // IDs shouldn't have invalid XML characters
            return key.match(/[&<>"']/);
        };

        self.keyHasError = function(key) {
            return self.isItemDuplicated(key) || self.hasBadXML(key);
        };

        self.hasError = function() {
            return self.duplicatedItems().length > 0
                || _.find(self.items(), function(i) { return self.hasBadXML(i.key()); });
        };

        self.getItems = function () {
            return _(self.items()).map(function (item) {
                return {
                    key: ko.utils.unwrapObservable(item.key),
                    value: _.object(_(item.value()).map(function (value, lang) {
                        return [lang, ko.utils.unwrapObservable(value)];
                    })),
                };
            });

        };
    };

    module.new = function (o) {
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
                },
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
        hqImport("hqwebapp/js/main").eventize(m);
        m.items.subscribe(function () {
            m.fire('change');
        });
        return m;
    };

    return module;

});
