hqDefine('app_manager/js/summary/menu', function() {
    var assertProperties = hqImport("hqwebapp/js/assert_properties").assert;

    var menuItemModel = function(options) {
        assertProperties(options, ['id', 'name', 'icon'], ['subitems', 'has_errors']);
        var self = _.extend({
            has_errors: false,
        }, options);

        self.isSelected = ko.observable(false);
        self.select = function() {
            self.isSelected(true);
        };

        return self;
    };

    var menuModel = function(options) {
        assertProperties(options, ['items', 'viewAllItems'], []);

        var self = {};

        self.items = options.items;
        self.viewAllItems = options.viewAllItems;

        self.selectedItemId = ko.observable('');      // blank indicates "View All"
        self.viewAllSelected = ko.computed(function() {
            return !self.selectedItemId();
        });

        self.select = function(item) {
            self.selectedItemId(item.id);
            _.each(self.items, function(i) {
                i.isSelected(item.id === i.id);
                _.each(i.subitems, function(s) {
                    s.isSelected(item.id === s.id);
                });
            });
        };
        self.selectAll = function() {
            self.select('');
        };

        return self;
    };

    return {
        menuItemModel: menuItemModel,
        menuModel: menuModel,
    };
});
