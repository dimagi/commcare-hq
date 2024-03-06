hqDefine('toggle_ui/js/edit-flag', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/main',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko',     // save button
], function (
    $,
    ko,
    _,
    initialPageData,
    hqMain
) {
    var PAD_CHAR = '&nbsp;';
    function toggleViewModel() {
        var self = {};
        self.items = ko.observableArray();
        self.randomness = ko.observable();

        self.init = function (config) {
            self.padded_ns = {};
            var maxLength = Math.max.apply(Math, _.map(config.namespaces, function (ns) { return ns.length; }));
            _(config.namespaces).each(function (namespace) {
                var diff = maxLength - namespace.length,
                    pad = new Array(diff + 1).join(PAD_CHAR);
                self.padded_ns[namespace] = namespace + pad;
            });
            self.init_items(config);
            self.latest_use = ko.observable(config.last_used._latest || '');
            self.randomness(config.randomness);
        };

        self.init_items = function (config) {
            var items = config.items,
                lastUsed = config.last_used || {},
                serviceType = config.service_type || {};
            self.items.removeAll();
            _.each(_.sortBy(items), function (item) {
                var fields = item.split(':'),
                    namespace = fields.length > 1 ? fields[0] : 'user',
                    value = fields.length > 1 ? fields[1] : fields[0];
                self.items.push({
                    namespace: ko.observable(self.padded_ns[namespace]),
                    value: ko.observable(value),
                    last_used: ko.observable(lastUsed[value]),
                    service_type: ko.observable(serviceType[value]),
                });
            });
        };

        self.addItem = function (namespace) {
            self.items.push({
                namespace: ko.observable(self.padded_ns[namespace]),
                value: ko.observable(),
                last_used: ko.observable(),
                service_type: ko.observable(),
            });
            self.change();
        };

        self.removeItem = function (item) {
            self.items.remove(item);
            self.change();
        };

        self.change = function () {
            self.saveButtonTop.fire('change');
            self.saveButtonBottom.fire('change');
        };

        self.createSaveButton = function () {
            return hqMain.initSaveButton({
                unsavedMessage: "You have unsaved changes",
                save: function () {
                    var items = _.map(_.filter(self.items(), function (item) {
                        return item.value();
                    }), function (item) {
                        var nsRaw = item.namespace().replace(new RegExp(PAD_CHAR, 'g'), ''),
                            namespace = nsRaw === 'user' ? null : nsRaw,
                            value = namespace === null ? item.value() : namespace + ':' + item.value();
                        return value;
                    });
                    self.saveButtonTop.ajax({
                        type: 'post',
                        url: initialPageData.reverse('edit_toggle') + location.search,
                        data: {
                            item_list: JSON.stringify(items),
                            randomness: self.randomness(),
                        },
                        dataType: 'json',
                        success: function (data) {
                            self.init_items(data);
                            self.saveButtonBottom.ajax({
                                success: function () {},
                            });
                        },
                    });

                },
            });
        };

        self.saveButtonTop = self.createSaveButton();
        self.saveButtonBottom = self.createSaveButton();

        var projectInfoUrl = '<a href="' + initialPageData.reverse('domain_internal_settings') + '">domain</a>';
        self.getNamespaceHtml = function (namespace, value) {
            if (namespace === 'domain') {
                return projectInfoUrl.replace('___', value);
            } else {
                return namespace;
            }
        };

        return self;
    }

    $(function () {
        var $home = $('#toggle_editing_ko');
        var view = toggleViewModel();
        view.init({
            items: initialPageData.get('items'),
            namespaces: initialPageData.get('namespaces'),
            last_used: initialPageData.get('last_used'),
            is_random_editable: initialPageData.get('is_random_editable'),
            randomness: initialPageData.get('randomness'),
            service_type: initialPageData.get('service_type'),
        });
        $home.koApplyBindings(view);
        $home.on('change', 'input', view.change);
    });
});
