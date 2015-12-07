var DrilldownOptionFilterControl = function (options) {
    var self = this;

    self.notification = new DrilldownFinalNotification(options.notifications);
    self.controls = ko.observableArray(ko.utils.arrayMap(options.controls, function (select) {
        return new DrilldownOption(select, options.drilldown_map);
    }));

    self.init = function () {
        for (var op = 0; op < options.selected.length; op++) {
            self.controls()[op].selected(options.selected[op]);
            self.updateNextDrilldown(self.controls()[op].level);
        }
    };

    self.updateNextDrilldown = function (trigger_level) {
        var current_control = self.controls()[trigger_level];
        var current_selection = current_control.selected(),
            current_options = current_control.control_options();

        if (trigger_level+1 === self.controls().length) {
            self.notification.changeMessage(current_selection);
            return null;
        }
        self.notification.changeMessage('');

        var current_index = _.indexOf(_.pluck(current_options, 'val'), current_selection);
        for (var l = trigger_level+1; l < self.controls().length; l++) {
            if (current_index >= 0 && l === trigger_level+1) {
                var next_options = current_options[current_index].next;
                self.controls()[trigger_level+1]
                    .selected(null)
                    .control_options(next_options);
            } else {
                if (self.controls()[l-1].selected() === void(0)) {
                    self.controls()[l].control_options([]);
                }
            }
        }
    };

};

var DrilldownFinalNotification = function (notifications) {
    var self = this;
    self.notifications = notifications;
    self.message = ko.observable();

    self.is_visible = ko.computed(function () {
        return !!self.message();
    });

    self.changeMessage = function (key) {
        self.message(self.notifications[key]);
        $('.drilldown-notification-tooltip').tooltip();
    };
};

var DrilldownOption = function (select, drilldown_map) {
    var self = this;
    self.label = select.label;
    self.default_text = select.default_text;
    self.slug = select.slug;
    self.level = select.level;

    self.control_options = ko.observableArray((self.level === 0) ? drilldown_map : []);
    self.selected = ko.observable();

    self.is_visible = ko.computed(function () {
        return !!(self.control_options().length) || self.selected() !== void(0);
    });

    self.show_next_drilldown = ko.computed(function () {
        return !(self.control_options().length) && self.selected() !== void(0);
    });
};

$.fn.drilldownOptionFilter = function (options) {
    var viewModel = new DrilldownOptionFilterControl(options);
    $(this).koApplyBindings(viewModel);
    viewModel.init();
};
