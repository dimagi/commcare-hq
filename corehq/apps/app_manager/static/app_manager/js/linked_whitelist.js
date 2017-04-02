/* globals hqDefine, ko, COMMCAREHQ */
hqDefine('app_manager/js/linked_whitelist.js', function () {
    function LinkedWhitelist(domains, saveUrl) {
        var self = this;
        this.linkedDomains = ko.observableArray(domains);
        this.saveButton = COMMCAREHQ.SaveButton.init({
            unsavedMessage: gettext("You have unsaved changes to your whitelist"),
            save: function () {
                self.saveButton.ajax({
                    url: saveUrl,
                    type: 'post',
                    data: {'whitelist': JSON.stringify(self.linkedDomains())},
                    error: function () {
                        throw gettext("There was an error saving");
                    },
                });
            },
        });
        var changeSaveButton = function () {
            self.saveButton.fire('change');
        };
        this.linkedDomains.subscribe(changeSaveButton);
        this.removeDomain = function(domain) {
            self.linkedDomains.remove(domain);
        };
    }
    return {LinkedWhitelist: LinkedWhitelist};
});
