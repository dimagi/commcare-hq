var PROGRESS_BAR_UPDATE_INTERVAL = 30000;


var ruleProgressBarGroup = function (progressUrl) {
    'use strict';
    var self = {};

    self.progressBars = {};

    self.add = function (handlerId, progressBar) {
        self.progressBars[handlerId] = progressBar;
    };

    self.updateProgress = function () {
        var request = $.ajax({
            url: progressUrl,
            type: "GET",
            dataType: "json",
        }).done(function (data, textStatus, jqXHR) {
            for (var handlerId in data) {
                if (handlerId in self.progressBars) {
                    var info = data[handlerId];
                    var progressBar = self.progressBars[handlerId];
                    progressBar.inProgress(!info.complete);
                    if (progressBar.inProgress()) {
                        progressBar.current(info.current);
                        progressBar.total(info.total);
                    }
                }
            }
        }).always(function (data, textStatus, jqXHR) {
            setTimeout(self.updateProgress, PROGRESS_BAR_UPDATE_INTERVAL);
        });
    };

    // Start the update progress loop
    self.updateProgress();

    return self;
};


var ruleProgressBar = function(handlerId, progressBarGroup) {
    'use strict';
    var self = {};

    self.inProgress = ko.observable(false);
    self.current = ko.observable(0);
    self.total = ko.observable(0);

    self.progressPct = ko.computed(function () {
        if (self.total() > 0) {
            return Math.round((self.current() / self.total()) * 100) + "%";
        } else {
            return "0%";
        }
    });

    self.progressDisplay = ko.computed(function () {
        return (self.current() || "?") + " / " + (self.total() || "?");
    });

    progressBarGroup.add(handlerId, self);

    return self;
};
