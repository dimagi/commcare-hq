(function () {

function MapList(o) {
    var self = this;
    self.lang = o.lang;
    self.langs = [o.lang].concat(o.langs);
    self.items = ko.observableArray();
    self.setItems = function (items) {
        self.items(_(items).map(function (item) {
            return {
                key: ko.observable(item.key),
                value: _.object(_(item.value).map(function (value, lang) {
                    return [lang, ko.observable(value)];
                }))
            };
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
        return {lang: null, value: null};
    };
    self.removeItem = function (item) {
        self.items.remove(item);
    };
    self.addItem = function () {
        var item = {key: ko.observable(''), value: {}};
        item.value[self.lang] = ko.observable('');
        self.items.push(item);
    };
    self.getItems = function () {
        return _(self.items()).map(function (item) {
            return {
                key: ko.utils.unwrapObservable(item.key),
                value: _.object(_(item.value).map(function (value, lang) {
                    return [lang, ko.utils.unwrapObservable(value)];
                }))
            };
        });

    };
}

uiElement.key_value_mapping = function (o) {
    var m = new MapList(o);
    m.edit = ko.observable(true);
    m.openModal = function () {
        // create a throw-away modal every time
        // lets us create a sandbox for editing that you can cancel
        var $modalDiv = $('<div data-bind="template: \'key_value_mapping_modal\'"></div>');
        var copy = new MapList({lang: o.lang, langs: o.langs, items: m.getItems()});
        ko.applyBindings({
            modalTitle: o.modalTitle,
            mapList: copy,
            save: function () {
                m.setItems(copy.getItems());
            }
        }, $modalDiv.get(0));
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
    ko.applyBindings(m, $div.get(0));
    m.ui = $div;
    eventize(m);
    m.items.subscribe(function () {
        m.fire('change');
    });
    return m;
};

}());