var PROGRESS_BAR_UPDATE_INTERVAL = 30000;


function RuleProgressBarGroup(progressUrl) {
    'use strict';
    var self = this;

    self.progress_bars = {};

    self.add = function(handler_id, progress_bar) {
        self.progress_bars[handler_id] = progress_bar;
    };

    self.update_progress = function() {
        var request = $.ajax({
            url: progressUrl,
            type: "GET",
            dataType: "json",
        }).done(function(data, textStatus, jqXHR) {
            for(var handler_id in data) {
                if(handler_id in self.progress_bars) {
                    var info = data[handler_id];
                    var progress_bar = self.progress_bars[handler_id];
                    progress_bar.in_progress(!info.complete);
                    if(progress_bar.in_progress()) {
                        progress_bar.current(info.current);
                        progress_bar.total(info.total);
                    }
                }
            }
        }).always(function(data, textStatus, jqXHR) {
            setTimeout(self.update_progress, PROGRESS_BAR_UPDATE_INTERVAL);
        });
    };

    // Start the update progress loop
    self.update_progress();
}


function RuleProgressBar(handler_id, progress_bar_group) {
    'use strict';
    var self = this;

    self.in_progress = ko.observable(false);
    self.current = ko.observable(0);
    self.total = ko.observable(0);

    self.progress_pct = ko.computed(function() {
        if(self.total() > 0) {
            return Math.round((self.current() / self.total()) * 100) + "%";
        } else {
            return "0%";
        }
    });

    self.progress_display = ko.computed(function() {
        return (self.current() || "?") + " / " + (self.total() || "?");
    });

    progress_bar_group.add(handler_id, self);
}
