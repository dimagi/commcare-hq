var DrilldownOptionFilterControl = function (options) {
    var self = this;
    console.log(options);
    self.drilldown_map = options.drilldown_map;

    self.controls = ko.observableArray(ko.utils.arrayMap(options.controls, function (select) {
        return new DrilldownOption(select, options.drilldown_map);
    }));

    self.updateNextDrilldown = function (trigger_level) {
        if (trigger_level+1 === self.controls().length)
            return;

        var current_control = self.controls()[trigger_level];
        var current_selection = current_control.selected(),
            current_options = current_control.control_options();
        var current_index = _.indexOf(_.pluck(current_options, 'val'), current_selection);
        for (var l = trigger_level+1; l < self.controls().length; l++) {
            self.controls()[l].selected(undefined);
            if (current_index >= 0 && l === trigger_level+1) {
                var next_options = current_options[current_index].next;
                self.controls()[trigger_level+1].control_options(next_options);
            } else {
                self.controls()[l].control_options([]);
            }
        }
    };

    for (var c in self.controls()) {
        self.controls()[c].initSelected(options.selected);
        self.updateNextDrilldown(self.controls()[c].level);
    }
};

var DrilldownOption = function(select, drilldown_map) {
    var self = this;
    self.label = select.label;
    self.default_text = select.default_text;
    self.slug = select.slug;
    self.level = select.level;
    var init_map = [];
    if (self.level === 0)
        init_map = drilldown_map;
    self.control_options = ko.observableArray(init_map);
    self.selected = ko.observable();
    self.is_visible = ko.computed(function () {
        return !!(self.control_options().length);
    });
    self.show_alert = ko.computed(function () {
        return !self.is_visible();
    });

    self.initSelected = function (selected_init) {
        var init_selected = undefined;
        if (self.level < selected_init.length) {
            init_selected = selected_init[self.level];
        }
        self.selected(init_selected);
    };
};

$.fn.drilldownOptionFilter = function (options) {
    this.each(function(i) {
        var viewModel = new DrilldownOptionFilterControl(options);
        ko.applyBindings(viewModel, $(this).get(i));
    });
};