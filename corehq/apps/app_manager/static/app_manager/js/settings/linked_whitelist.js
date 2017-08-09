/* globals hqDefine, ko */
hqDefine('app_manager/js/settings/linked_whitelist.js', function () {
    function LinkedWhitelist(domains, saveUrl) {
        var self = this;
        this.linkedDomains = ko.observableArray(domains);
        this.saveButton = hqImport("style/js/main.js").initSaveButton({
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
            var domains = hqImport("hqwebapp/js/initial_page_data.js").get("linked_whitelist");
            var save = hqImport("hqwebapp/js/urllib.js").reverse("update_linked_whitelist");
            linkedWhitelist = new LinkedWhitelist(domains, save);
            $whitelistTab.koApplyBindings(linkedWhitelist);
        }
    });
});
