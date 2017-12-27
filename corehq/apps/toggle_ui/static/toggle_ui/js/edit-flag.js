/* globals hqDefine */
hqDefine('toggle_ui/js/edit-flag', function () {
    var PAD_CHAR = '&nbsp;';
    function ToggleView() {
        var self = this;
        self.items = ko.observableArray();
        self.randomness = ko.observable();

        self.init = function (config) {
            self.padded_ns = {};
            var max_ns_len = Math.max.apply(Math, _.map(config.namespaces, function (ns) { return ns.length }));
            _(config.namespaces).each(function (namespace) {
                var diff = max_ns_len - namespace.length,
                    pad = new Array(diff + 1).join(PAD_CHAR);
                self.padded_ns[namespace] = namespace + pad;
            });
            self.init_items(config);
            self.latest_use = ko.observable(config.last_used._latest || '');
            self.randomness(config.randomness);
        };

        self.init_items = function (config) {
            var items = config.items,
                last_used = config.last_used || {};
            self.items.removeAll();
            _(items).each(function (item) {
                var fields = item.split(':'),
                    namespace = fields.length > 1 ? fields[0] : 'user',
                    value = fields.length > 1 ? fields[1] : fields[0];
                self.items.push({
                    namespace: ko.observable(self.padded_ns[namespace]),
                    value: ko.observable(value),
                    last_used: ko.observable(last_used[value])
                });
            });
        };

        self.addItem = function (namespace) {
            self.items.push({
                namespace: ko.observable(self.padded_ns[namespace]),
                value: ko.observable(),
                last_used: ko.observable()
            });
            self.change();
        };

        self.removeItem = function (item) {
            self.items.remove(item);
            self.change();
        };

        self.change = function () {
            self.saveButton.fire('change');
        };

        self.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
            unsavedMessage: "You have unsaved changes",
            save: function () {
                var items = _.map(self.items(), function (item) {
                    var ns_raw = item.namespace().replace(new RegExp(PAD_CHAR, 'g'), ''),
                        namespace = ns_raw === 'user' ? null : ns_raw,
                        value = namespace === null ? item.value() : namespace + ':' + item.value();
                    return value;
                });
                self.saveButton.ajax({
                    type: 'post',
                    url: hqImport('hqwebapp/js/initial_page_data').reverse('edit_toggle') + location.search,
                    data: {
                        item_list: JSON.stringify(items),
                        randomness: self.randomness(),
                    },
                    dataType: 'json',
                    success: function (data) {
                        self.init_items(data);
                    }
                });
            }
        });

        var projectInfoUrl = '<a href="' + hqImport('hqwebapp/js/initial_page_data').reverse('domain_internal_settings') + '">domain</a>';
        self.getNamespaceHtml = function(namespace, value) {
            if (namespace === 'domain') {
                return projectInfoUrl.replace('___', value);
            } else {
                return namespace;
            }
        };

    }

    $(function(){
        var $home = $('#toggle_editing_ko');
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get,
            view = new ToggleView();
        view.init({
            items: initial_page_data('items'),
            namespaces: initial_page_data('namespaces'),
            last_used: initial_page_data('last_used'),
            is_random_editable: initial_page_data('is_random_editable'),
            randomness: initial_page_data('randomness'),
        });
        $home.koApplyBindings(view);
        $home.on('change', 'input', view.change);
    });
});
