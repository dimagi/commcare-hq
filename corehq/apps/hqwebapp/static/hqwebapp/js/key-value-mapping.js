(function () {

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
        return makeSafeForCSS(this.key());
    }, this);


    // util function to generate icon-name of the format "module<module_id>_list_icon_<property_name>_<hash_of_item.key>"
    this.generateIconPath = function(){
        var randomFourDigits = Math.floor(Math.random()*9000) + 1000;;
        var iconPrefix =  "jr://file/commcare/image/module" + mappingContext.module_id + "_list_icon_" + mappingContext.property_name.val() + "_";
        return iconPrefix + randomFourDigits + ".png";
    };


    var app_manager = hqImport('app_manager/js/app_manager_media.js');
    var uploaders = hqImport('#app_manager/partials/nav_menu_media_js_common.html');
    // attach a media-manager if item.value is a file-path to icon
    if (mappingContext.values_are_icons) {
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
            if (mappingContext.values_are_icons && lang === mappingContext.lang){
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
    self.values_are_icons = o.values_are_icons || false;
    self.multimedia = o.multimedia;
    self.property_name = o.property_name;

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
        return {lang: null, value: 'icon path'};
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

uiElement.key_value_mapping = function (o) {
    var m = new MapList(o);
    m.edit = ko.observable(true);
    m.buttonText = o.buttonText || "Edit",
    m.values_are_icons = o.values_are_icons || false;
    m.openModal = function () {
        // create a throw-away modal every time
        // lets us create a sandbox for editing that you can cancel
        var $modalDiv = $('<div data-bind="template: \'key_value_mapping_modal\'"></div>');
        var copy = new MapList({
            lang: o.lang,
            langs: o.langs,
            module_id: o.module_id,
            items: m.getItems(),
            values_are_icons: m.values_are_icons,
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
        $modal.modal('show');
        $modal.on('hidden', function () {
            $modal.remove();
        });
    };
    m.setEdit = function (edit) {
        m.edit(edit);
    };
    var $div = $('<div data-bind="template: \'key_value_mapping_template\'"></div>');
    $div.koApplyBindings(m);
    m.ui = $div;
    eventize(m);
    m.items.subscribe(function () {
        m.fire('change');
    });
    return m;
};

}());


// To stack icon-uploader modal on top of key-value-mapping modal
// Hide modal into the stack
$(document).on('show.bs.modal', '#hqimage', function () {
    var $km = $(".modal.in");
    $km.addClass("stacked-modal");
    $km.hide();
});
// Pop out hidden stack onto top
$(document).on('hide.bs.modal', '#hqimage', function () {
    var $km = $(".stacked-modal");
    $km.removeClass("stacked-modal");
    $km.show();
});


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
