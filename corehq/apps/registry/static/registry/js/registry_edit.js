hqDefine("registry/js/registry_edit", [
    'moment',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'registry/js/registry_text',
    'registry/js/registry_actions',
    'hqwebapp/js/components.ko',  // inline-edit
    'hqwebapp/js/select2_knockout_bindings.ko',
    'hqwebapp/js/knockout_bindings.ko', // openModal
], function (
    moment,
    ko,
    _,
    initialPageData,
    alertUser,
    text,
    actions,
) {
    let InvitationModel = function(data) {
        let self = data;
        self.statusText = text.getStatusText(self.status);
        self.cssIcon = text.getStatusIcon(self.status);
        self.cssClass = text.getStatusCssClass(self.status);
        self.invitationDate = moment(self.created_on).format("D MMM YYYY");
        self.responseDate = "";
        if (self.rejected_on) {
            self.responseDate = moment(self.rejected_on).format("D MMM YYYY");
        } else if (self.accepted_on) {
            self.responseDate = moment(self.accepted_on).format("D MMM YYYY");
        }

        return self;
    }
    let GrantModel = function(currentDomain, data) {
        let self = data;
        self.canDelete = self.from_domain === currentDomain;
        return self;
    }
    let EditModel = function(data, availableCaseTypes, availableDomains) {
        const mapping = {
            'copy': ["domain", "slug", "name", "description"],
            'observe': ["is_active", "schema", "invitations", "grants"],
            invitations: {
                create: (options) => InvitationModel(options.data)
            },
            grants: {
                create: (options) => GrantModel(data.domain, options.data)
            }
        };
        let self = ko.mapping.fromJS(data, mapping);
        self.availableCaseTypes = availableCaseTypes;
        self.availableInviteDomains = ko.computed(() => {
            const invited = self.invitations().map((invite) => invite.domain);
            return availableDomains.filter((domain) => !invited.includes(domain));
        });
        self.availableGrantDomains = ko.computed(() => {
             return self.invitations().map((invite) => invite.domain);
        });
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
                   self.grants.push(GrantModel(self.domain, grant));
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
        return self;
    }

    $(function () {
        $("#edit-registry").koApplyBindings(EditModel(
            initialPageData.get("registry"),
            initialPageData.get("availableCaseTypes"),
            initialPageData.get("availableDomains"),
        ));
    });
});
