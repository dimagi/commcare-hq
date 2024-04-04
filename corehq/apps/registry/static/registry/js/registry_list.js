hqDefine("registry/js/registry_list", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'registry/js/registry_text',
    'registry/js/registry_actions',
    'hqwebapp/js/bootstrap5/knockout_bindings.ko', // openModal
    'hqwebapp/js/select2_knockout_bindings.ko',
], function (
    $,
    _,
    ko,
    initialPageData,
    text,
    actions
) {

    let OwnedDataRegistry = function (registry) {
        let self = ko.mapping.fromJS(registry);
        self.acceptedText = ko.computed(function() {
            return text.getAcceptedBadgeText(self);
        });
        self.pendingText = ko.computed(function() {
            return text.getPendingBadgeText(self);
        });
        self.rejectedText = ko.computed(function() {
            return text.getRejectedBadgeText(self);
        });
        self.manageUrl = initialPageData.reverse('manage_registry', self.slug())

        return self;
    };

    let InvitedDataRegistry = function (registry) {
        let self = ko.mapping.fromJS(registry);
        self.participatorCountText = ko.computed(function() {
            return text.getParticipatorCountBadgeText(self);
        });
        self.statusText = ko.computed(function() {
            return text.getStatusText(self.invitation.status());
        });

        self.manageUrl = initialPageData.reverse('manage_registry', self.slug())

        self.acceptInvitation = function() {
            actions.acceptInvitation(self.slug, (data) => {
                ko.mapping.fromJS(data, self);
            });
        }

        self.rejectInvitation = function() {
            actions.rejectInvitation(self.slug, (data) => {
                ko.mapping.fromJS(data, self);
            });
        }
        return self;
    };

    let dataRegistryList = function ({ownedRegistries, invitedRegistries}) {
        let self = {
            ownedRegistries: _.map(ownedRegistries, (registry) => OwnedDataRegistry(registry)),
            invitedRegistries: _.map(invitedRegistries, (registry) => InvitedDataRegistry(registry)),
            availableCaseTypes: initialPageData.get("availableCaseTypes"),
        };

        // CREATE workflow
        self.name = ko.observable("").extend({
            rateLimit: { method: "notifyWhenChangesStop", timeout: 400, }
        });

        self.validatingPending = ko.observable(false);
        self.nameValid = ko.observable(false);
        self.nameChecked = ko.observable(false);
        self.name.subscribe((value) => {
            self.validatingPending(true);
            actions.validateName(value, (isValid) => {
                self.nameValid(isValid);
                self.nameChecked(true);
            }).always(() => {
                self.validatingPending(false);
            });
        });

        self.caseTypes = ko.observable([]);
        self.formCreateRegistrySent = ko.observable(false);
        self.submitCreate = function () {
            self.formCreateRegistrySent(true);
            return true;
        };
        return self;
    }
    $(function () {
        $("#data-registry-list").koApplyBindings(dataRegistryList({
            ownedRegistries: initialPageData.get("owned_registries"),
            invitedRegistries: initialPageData.get("invited_registries"),
        }));
    });
});
