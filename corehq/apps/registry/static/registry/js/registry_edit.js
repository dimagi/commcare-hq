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
    'hqwebapp/js/main.ko', // makeHqHelp
], function (
    moment,
    ko,
    _,
    initialPageData,
    alertUser,
    text,
    actions,
    inlineEdit,
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
        self.invitationStatusText = ko.computed(() => {
            return text.getStatusText(self.domain_invitation.status());
        });
        self.invitationStatusClass = ko.computed(() => {
            return text.getStatusCssClass(self.domain_invitation.status());
        });
        self.showAccept = ko.computed(() => {
            return ['pending', 'rejected'].includes(self.domain_invitation.status());
        })
        self.showReject = ko.computed(() => {
            return ['pending', 'accepted'].includes(self.domain_invitation.status());
        })
        self.availableCaseTypes = availableCaseTypes;
        self.availableInviteDomains = ko.computed(() => {
            const existingInvites = self.invitations().map((invite) => invite.domain);
            return availableDomains.filter((domain) => !existingInvites.includes(domain));
        });
        self.availableGrantDomains = ko.computed(() => {
            let availableDomains = new Set(invitedDomains.concat(self.invitations().map((invite) => invite.domain)));
            availableDomains.delete(self.current_domain);
            return Array.from(availableDomains);
        });

        self.toggleActiveState = function() {
            actions.editAttr(self.slug, "is_active", {"value": !self.is_active()}, (data) => {
                self.is_active(data.is_active);
            });
        }

        self.inviteDomains = ko.observable([]);
        self.removeDomain = function (toRemove){
            actions.removeInvitation(self.slug, toRemove.id, toRemove.domain, () => {
                self.invitations(self.invitations().filter((invite) => {
                    return invite.id !== toRemove.id;
                }));
            });
        }

        self.addDomain = function () {
            actions.addInvitations(self.slug, self.inviteDomains(), (data) => {
                _.each(data.invitations, (invite) => {
                   self.invitations.unshift(InvitationModel(invite));
                });
                self.inviteDomains([]);
            })
        }

        self.editedSchema = ko.observable(self.schema());
        self.saveSchema = function () {
            actions.editAttr(self.slug, 'schema', {"value": self.editedSchema()}, (data) => {
                self.schema(self.editedSchema());
            })
        }

        self.grantDomains = ko.observable([]);
        self.createGrant = function() {
            actions.createGrant(self.slug, self.grantDomains(), (data) => {
                _.each(data.grants, (grant) => {
                   self.grants.unshift(GrantModel(self.current_domain, grant));
                });
                self.grantDomains([]);
            })
        }

        self.removeGrant = function(toRemove) {
            actions.removeGrant(self.slug, toRemove.id, () => {
                self.grants(self.grants().filter((grant) => {
                    return grant.id !== toRemove.id;
                }));
            });
        }

        self.acceptInvitation = function() {
            actions.acceptInvitation(self.slug, (data) => {
                ko.mapping.fromJS({"domain_invitation": data.invitation}, self);
            });
        }

        self.rejectInvitation = function() {
            actions.rejectInvitation(self.slug, (data) => {
                ko.mapping.fromJS({"domain_invitation": data.invitation}, self);
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
