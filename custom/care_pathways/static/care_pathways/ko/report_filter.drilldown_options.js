var DrilldownOptionFilterControl = function (options) {
    var self = this;

    self.notification = new DrilldownFinalNotification(options.notifications);
    self.controls = ko.observableArray(ko.utils.arrayMap(options.controls, function (select) {
        return new DrilldownOption(select, options.drilldown_map);
    }));

    self.init = function () {
        console.log(options);
        for (var op = 0; op < options.selected.length; op++) {
            console.log(self.controls()[op].selected(options.selected[op]));
            self.controls()[op].selected(options.selected[op]);
            self.updateNextDrilldown(self.controls()[op].level);
        }
    };

    self.updateNextDrilldown = function (trigger_level) {
        var current_control = self.controls()[trigger_level];
        var current_selection = current_control.selected(),
            current_options = current_control.control_options();
        console.log(current_control);
        if (trigger_level+1 === self.controls().length) {
            for(var i=0; i < current_selection.length; i++) {
                self.notification.changeMessage(current_selection[i]);
            }
            return null;
        }
        self.notification.changeMessage('');

        if (current_selection.length == 0) {
            self.controls()[trigger_level + 1].selected.removeAll();
            self.controls()[trigger_level + 1].control_options([]);
        }
        else {
            var next_options = []
            for (var op = 0; op < current_selection.length; op++) {
                self.controls()[op].selected([]);
            }



            for(var i=0; i < current_selection.length; i++) {
                var current_index = _.indexOf(_.pluck(current_options, 'val'), current_selection[i]);

                for (var l = trigger_level+1; l < self.controls().length; l++) {
                    if (current_index >= 0 && l === trigger_level+1) {
                        next_options.push.apply(next_options, current_options[current_index].next);
                        self.controls()[trigger_level+1].control_options(next_options);
                    } else {
                        self.controls()[l].control_options([]);
                    }
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
    self.selected = ko.observableArray();

    self.is_visible = ko.computed(function () {
        return !!(self.control_options().length);
    });

    self.show_next_drilldown = ko.computed(function () {
        return !(self.control_options().length);
    });
};

$.fn.drilldownOptionFilter = function (options) {
    this.each(function(i) {
        var viewModel = new DrilldownOptionFilterControl(options);
        ko.applyBindings(viewModel, $(this).get(i));
        viewModel.init();
    });
};