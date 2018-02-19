/* globals hqDefine, ko */
hqDefine('app_manager/js/settings/linked_whitelist', function () {
    function LinkedWhitelist(domains, saveUrl) {
        var self = this;
        this.linkedDomains = ko.observableArray(domains);
        this.saveButton = hqImport("hqwebapp/js/main").initSaveButton({
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

    $(function () {
        var $whitelistTab = $('#linked-whitelist');
        if ($whitelistTab.length) {
            var domains = hqImport("hqwebapp/js/initial_page_data").get("linked_whitelist");
            var save = hqImport("hqwebapp/js/initial_page_data").reverse("update_linked_whitelist");
            var linkedWhitelist = new LinkedWhitelist(domains, save);
            $whitelistTab.koApplyBindings(linkedWhitelist);
        }
    });
});
