hqDefine('reports/js/filters/bootstrap5/drilldown_options', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/bootstrap5/knockout_bindings.ko',  // fadeVisible
], function (
    $,
    ko,
    _,
) {
    var drilldownOptionFilterControl = function (options) {
        var self = {};

        self.notification = drilldownFinalNotification(options.notifications);
        self.controls = ko.observableArray(ko.utils.arrayMap(options.controls, function (select) {
            return drilldownOption(select, options.drilldown_map);
        }));

        self.init = function () {
            for (var op = 0; op < options.selected.length; op++) {
                self.controls()[op].selected(options.selected[op]);
                self.updateNextDrilldown(self.controls()[op].level);
            }
        };

        self.updateNextDrilldown = function (triggerLevel) {
            var currentControl = self.controls()[triggerLevel];
            var currentSelection = currentControl.selected(),
                currentOptions = currentControl.control_options();

            if (triggerLevel + 1 === self.controls().length) {
                self.notification.changeMessage(currentSelection);
                return null;
            }
            self.notification.changeMessage('');

            var currentIndex = _.indexOf(_.pluck(currentOptions, 'val'), currentSelection);
            for (var l = triggerLevel + 1; l < self.controls().length; l++) {
                if (currentIndex >= 0 && l === triggerLevel + 1) {
                    var nextOptions = currentOptions[currentIndex].next;
                    self.controls()[triggerLevel + 1]
                        .selected(null)
                        .control_options(nextOptions);
                } else {
                    if (self.controls()[l - 1].selected() === void(0)) {
                        self.controls()[l].control_options([]);
                    }
                }
            }
        };
        return self;
    };

    var drilldownFinalNotification = function (notifications) {
        var self = {};
        self.notifications = notifications;
        self.message = ko.observable();

        self.is_visible = ko.computed(function () {
            return !!self.message();
        });

        self.changeMessage = function (key) {
            self.message(self.notifications[key]);
            $('.drilldown-notification-tooltip').tooltip();  /* todo B5: plugin:tooltip */
        };
        return self;
    };

    var drilldownOption = function (select, drilldownMap) {
        var self = {};
        self.label = select.label;
        self.default_text = select.default_text;
        self.slug = select.slug;
        self.level = select.level;

        self.control_options = ko.observableArray((self.level === 0) ? drilldownMap : []);
        self.selected = ko.observable();

        self.is_visible = ko.computed(function () {
            return !!(self.control_options().length) || self.selected() !== void(0);
        });

        self.show_next_drilldown = ko.computed(function () {
            return !(self.control_options().length) && self.selected() !== void(0);
        });
        return self;
    };

    return { drilldownOptionFilterControl: drilldownOptionFilterControl };
});
