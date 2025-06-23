import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";

function casePropertyWarningViewModel (propertyLimit) {
    self.caseType = '';
    self.propertyCount = 0;
    self.propertyLimit = propertyLimit;
    self.showWarning = ko.observable(false);
    self.warningContent = ko.observable();

    self.updateViewModel = function(caseType, propertyCount) {
        self.caseType = caseType;
        self.propertyCount = propertyCount;
        self.updateWarningText();
        self.showWarningIfNecessary();
    };

    self.updateWarningText = function() {
        let content = _.template(gettext(
            "The '<%- type %>' case has a total of <%- count %> custom properties. " +
            "We recommend at most <%- limit %> custom properties per case type, " +
            "otherwise you may run into performance issues at the time of data collection and analysis."
        ))({
            type: self.caseType,
            count: self.propertyCount,
            limit: self.propertyLimit,
        });
        self.warningContent(content);
    };

    self.showWarningIfNecessary = function() {
        const shouldShow = self.propertyCount > self.propertyLimit;
        self.showWarning(shouldShow);
    };

    $('#performance-warning-content').on('show.bs.collapse', function () {
        $('#performance-warning-toggle i')
            .removeClass('fa-chevron-down')
            .addClass('fa-chevron-up');
    });

    $('#performance-warning-content').on('hide.bs.collapse', function () {
        $('#performance-warning-toggle i')
            .removeClass('fa-chevron-up')
            .addClass('fa-chevron-down');
    });

    self.updateViewModel(self.caseType, self.propertyCount);

    return self;
};

export default casePropertyWarningViewModel;
