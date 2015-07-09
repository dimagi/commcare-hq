var PROGRESS_BAR_UPDATE_INTERVAL = 15000;


function RuleProgressBarList() {
    'use strict';
    var self = this;

    self.progress_bars = [];
    self.index = 0;

    self.add = function(progress_bar) {
        self.progress_bars.push(progress_bar);
    };

    self.update_progress = function() {
        if(self.progress_bars.length === 0) {
            // If there are no RuleProgressBars in the list, then just call
            // this method again, and keep doing so until there is at least
            // one RuleProgressBar.
            setTimeout(self.update_progress, PROGRESS_BAR_UPDATE_INTERVAL);
        } else {
            // Now that there is at least one element, we're going to call
            // update_progress() on the next RuleProgressBar in the list,
            // and since each call to update_progress() sets the next timeout,
            // we're calling update_progress() on each RuleProgressBar one at a
            // time every PROGRESS_BAR_UPDATE_INTERVAL milliseconds.
            var next = self.progress_bars[self.index];
            self.index++;
            if(self.index >= self.progress_bars.length) {
                self.index = 0;
            }
            next.update_progress();
        }
    };

    // Start the update progress loop
    self.update_progress();
}


var progress_bar_list = new RuleProgressBarList();


function RuleProgressBar(handler_id, ajaxURL) {
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

    self.update_progress = function() {
        var request = $.ajax({
            url: ajaxURL,
            type: "GET",
            async: false,
            dataType: "json",
            data: {
                "handler_id": handler_id,
            },
        }).done(function(data, textStatus, jqXHR) {
            if(data.success) {
                self.in_progress(!data.complete);
                if(self.in_progress()) {
                    self.current(data.current);
                    self.total(data.total);
                }
            }
        }).always(function(data, textStatus, jqXHR) {
            // Setup the call to update_progress() which will update the next
            // RuleProgressBar in the list. We have to do this here to make
            // sure we always wait until the ajax request is completely done.
            setTimeout(progress_bar_list.update_progress, PROGRESS_BAR_UPDATE_INTERVAL);
        });
    }

    progress_bar_list.add(self);
}
