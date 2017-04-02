//probably we need clear this file
//copy/paste from https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reports/static/reports/js/report_filter.drilldown_options.js

ko.bindingHandlers.select2 = {
    init: function(el, valueAccessor, allBindingsAccessor, viewModel) {
      ko.utils.domNodeDisposal.addDisposeCallback(el, function() {
        $(el).select2('destroy');
      });

      var allBindings = allBindingsAccessor(),
          select2 = ko.utils.unwrapObservable(allBindings.select2);

      $(el).select2(select2);
    },
    update: function (el, valueAccessor, allBindingsAccessor, viewModel) {
        var allBindings = allBindingsAccessor();

        if ("value" in allBindings) {
            $(el).select2("data", allBindings.value());
        } else if ("selectedOptions" in allBindings) {
            var converted = [];
            var textAccessor = function(value) {
                return value; };
            if ("optionsText" in allBindings) {
                textAccessor = function(value) {
                    var valueAccessor = function (item) { return item; }
                    if ("optionsValue" in allBindings) {
                        valueAccessor = function (item) { return item[allBindings.optionsValue]; }
                    }
                    var items = $.grep(allBindings.options(), function (e) { return valueAccessor(e) == value});
                    if (items.length == 0 || items.length > 1) {
                        return ''
                    } else {
                        return items[0][allBindings.optionsText];
                    }
                }
            }
            $.each(allBindings.selectedOptions(), function (key, value) {
                if (textAccessor(value) !== '') {
                    converted.push({id: value, text: textAccessor(value)});
                }
            });
            converted = _.uniq(converted, function(obj) {return obj.id});
            var data = $(el).select2('data');
            if (data.length === _.uniq(allBindings.selectedOptions()).length) {
                if (_.indexOf(_.pluck(data, 'id'), 'all') === 0 && data.length > 1) {
                    converted.splice(0, 1)
                } else if ((_.indexOf(_.pluck(data, 'id'), 'all') + 1) === data.length && converted.length > 1) {
                    converted = converted[_.indexOf(_.pluck(converted, 'id'), 'all')];
                    var tmplist = allBindings.selectedOptions().slice();
                    $.each(tmplist, function (key, value) {
                        if (textAccessor(value) !== '' && value !== 'all') {
                            allBindings.selectedOptions().pop()
                        }
                    });
                }
            }

            $(el).select2("data", converted);
        }
    }
};

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
            for(var i=0; i < current_selection.length; i++) {
                self.notification.changeMessage(current_selection[i]);
            }
            return null;
        }
        self.notification.changeMessage('');

        if (current_selection.length == 0) {
            self.controls()[trigger_level + 1].selected.removeAll();
            self.controls()[trigger_level + 1].control_options([]);
            self.updateNextDrilldown(self.controls()[trigger_level + 1].level);
        }
        else {
            var next_options = [];
            for(var i=0; i < current_selection.length; i++) {
                var current_index = _.indexOf(_.pluck(current_options, 'val'), current_selection[i]);

                for (var l = trigger_level+1; l < self.controls().length; l++) {
                    if (current_index >= 0 && l === trigger_level+1) {
                        next_options.push.apply(next_options, current_options[current_index].next);
                        self.controls()[trigger_level+1].control_options(_.uniq(next_options, function(obj) {return obj.val}));
                    } else {
                        self.controls()[l].control_options([]);
                    }
                }
            }
        }
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
        if (!(self.control_options().length)) {
            self.selected.removeAll();
        }
        if (self.selected.length === 0){
            self.selected.push("all");
        }
        return !!(self.control_options().length);
    });

    self.show_next_drilldown = ko.computed(function () {
        return !(self.control_options().length);
    });
};

$.fn.drilldownOptionFilter = function (options) {
    var viewModel = new DrilldownOptionFilterControl(options);
    $(this).koApplyBindings(viewModel);
    viewModel.init();
};
