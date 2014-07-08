function RuleProgressBar(handler_id, ajaxURL) {
    'use strict';
    var self = this;

    self.in_progress = ko.observable(false);
    self.current = ko.observable(0);
    self.total = ko.observable(0);

    self.progress_pct = ko.computed(function() {
        if(self.total() > 0) {
            return (self.current() / self.total()) * 100 + "%";
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
            setTimeout(self.update_progress, 15000);
        });
    }

    self.update_progress();

}
