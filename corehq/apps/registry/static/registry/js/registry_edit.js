hqDefine("registry/js/registry_edit", [
    'moment',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'registry/js/registry_text',
    'registry/js/registry_actions',
    'hqwebapp/js/components/inline_edit',
    'hqwebapp/js/select2_knockout_bindings.ko',
    'hqwebapp/js/knockout_bindings.ko', // openModal
    'hqwebapp/js/main', // makeHqHelp
    'hqwebapp/js/multiselect_utils',
], function (
    moment,
    ko,
    _,
    initialPageData,
    alertUser,
    text,
    actions,
    inlineEdit
) {
    ko.components.register('inline-edit', inlineEdit);

    let InvitationModel = function(data) {
        let self = data;
        self.statusText = text.getStatusText(self.status);
        self.cssIcon = text.getStatusIcon(self.status);
        self.cssClass = text.getStatusCssClass(self.status);
        self.invitationDate = moment(self.created_on).format("D MMM YYYY");
        self.responseDate = moment(self.modified_on).format("D MMM YYYY");
        return self;
    }
    let GrantModel = function(currentDomain, data) {
        let self = data;
        self.canDelete = self.from_domain === currentDomain;
        return self;
    }
    let EditModel = function(data, availableCaseTypes, availableDomains, invitedDomains) {
        const mapping = {
            'copy': ["domain", "current_domain", "is_owner", "slug", "description"],
            'observe': ["name", "is_active", "schema", "invitations", "grants", "domain_invitation"],
            invitations: {
                create: (options) => InvitationModel(options.data)
            },
            grants: {
                create: (options) => GrantModel(data.current_domain, options.data)
            }
        };
        const grantSort = (a, b) => {
            // show grants for current domain at the top
            if (a.from_domain === b.from_domain) {
                return 0;
            } else if (a.from_domain === data.current_domain) {
                return -1;
            }
            return 1;
        };

        let self = ko.mapping.fromJS(data, mapping);
        self.sortedGrants = ko.computed(() => {
            return self.grants().sort(grantSort);
        });
        self.invitationStatusText = ko.computed(() => text.getStatusText(self.domain_invitation.status()));
        self.invitationStatusClass = ko.computed(() => text.getStatusCssClass(self.domain_invitation.status()));
        self.showAccept = ko.computed(() => ['pending', 'rejected'].includes(self.domain_invitation.status()));
        self.showReject = ko.computed(() => ['pending', 'accepted'].includes(self.domain_invitation.status()));

        self.availableCaseTypes = availableCaseTypes;
        self.availableInviteDomains = ko.computed(() => {
            const existingInvites = self.invitations().map((invite) => invite.domain);
            return availableDomains.filter((domain) => {
                return domain !== self.current_domain && !existingInvites.includes(domain)
            });
        });
        self.availableGrantDomains = ko.computed(() => {
            // use invitedDomains since invitations() will be empty if the current domain is not the owner
            let availableDomains = new Set(invitedDomains.concat(self.invitations().map((invite) => invite.domain))),
                granted = self.grants().filter((grant) => grant.from_domain === self.current_domain).flatMap((grant) => {
                    return grant.to_domains
                });
            availableDomains.delete(self.current_domain);
            granted.forEach((domain) => availableDomains.delete(domain));
            return Array.from(availableDomains);
        });

        self.savingActiveState = ko.observable(false);
        self.toggleActiveState = function() {
            self.savingActiveState(true);
            actions.editAttr(self.slug, "is_active", {"value": !self.is_active()}, (data) => {
                self.is_active(data.is_active);
            }).done(() => {
                self.savingActiveState(false);
            });
        }

        self.inviteDomains = ko.observable([]);
        self.removeDomain = function (toRemove){
            self.modalSaving(true);
            actions.removeInvitation(self.slug, toRemove.id, toRemove.domain, () => {
                self.invitations(self.invitations().filter((invite) => {
                    return invite.id !== toRemove.id;
                }));
            }).done(() => {
                self.modalSaving(false);
                $(".modal").modal('hide');
            });
        }

        self.addDomain = function () {
            self.modalSaving(true);
            actions.addInvitations(self.slug, self.inviteDomains(), (data) => {
                _.each(data.invitations, (invite) => {
                   self.invitations.unshift(InvitationModel(invite));
                });
                self.inviteDomains([]);
            }).always(() => {
                self.modalSaving(false);
                $(".modal").modal('hide');
            });
        }

        self.editedSchema = ko.observable(self.schema());
        self.modalSaving = ko.observable(false);
        self.saveSchema = function () {
            self.modalSaving(true);
            actions.editAttr(self.slug, 'schema', {"value": self.editedSchema()}, () => {
                self.schema(self.editedSchema());
            }).always(() => {
                self.modalSaving(false);
                $(".modal").modal('hide');
            });
        }

        self.grantDomains = ko.observable([]);
        self.createGrant = function() {
            self.modalSaving(true);
            actions.createGrant(self.slug, self.grantDomains(), (data) => {
                _.each(data.grants, (grant) => {
                   self.grants.unshift(GrantModel(self.current_domain, grant));
                });
                self.grantDomains([]);
            }).always(() => {
                self.modalSaving(false);
                $(".modal").modal('hide');
            });
        }

        self.removeGrant = function(toRemove) {
            self.modalSaving(true);
            actions.removeGrant(self.slug, toRemove.id, () => {
                self.grants(self.grants().filter((grant) => {
                    return grant.id !== toRemove.id;
                }));
            }).always(() => {
                self.modalSaving(false);
                $(".modal").modal('hide');
            });
        }

        self.savingInvitation = ko.observable(false);
        self.acceptInvitation = function() {
            self.savingInvitation(true);
            actions.acceptInvitation(self.slug, (data) => {
                ko.mapping.fromJS({"domain_invitation": data.invitation}, self);
            }).always(() => {
                self.savingInvitation(false);
            });
        }

        self.rejectInvitation = function() {
            self.savingInvitation(true);
            actions.rejectInvitation(self.slug, (data) => {
                ko.mapping.fromJS({"domain_invitation": data.invitation}, self);
            }).always(() => {
                self.savingInvitation(false);
            });
        }

        // DELETE workflow
        self.formDeleteRegistrySent = ko.observable(false);
        self.signOffDelete = ko.observable('');
        self.deleteDisabled = ko.computed(() => {
            return self.formDeleteRegistrySent() || self.signOffDelete().toLowerCase() !== self.name().toLowerCase();
        });
        self.submitDelete = function () {
            if (!self.deleteDisabled()) {
                self.formDeleteRegistrySent(true);
                return true;
            }
        };

        return self;
    }

    $(function () {
        $("#edit-registry").koApplyBindings(EditModel(
            initialPageData.get("registry"),
            initialPageData.get("availableCaseTypes"),
            initialPageData.get("availableDomains"),
            initialPageData.get("invitedDomains"),
        ));
    });
});
