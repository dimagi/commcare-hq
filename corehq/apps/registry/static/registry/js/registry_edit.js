hqDefine("registry/js/registry_edit", [
    'moment',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'registry/js/registry_text',
    'hqwebapp/js/components.ko',  // inline-edit
    'hqwebapp/js/select2_knockout_bindings.ko',
    'hqwebapp/js/knockout_bindings.ko', // openModal
], function (
    moment,
    ko,
    initialPageData,
    text,
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
    let GrantModel = function(data) {
        let self = data;
        return self;
    }
    let EditModel = function(caseTypes, availableCaseTypes, invitations, grants) {
        let self = this;
        self.caseTypes = ko.observable(caseTypes);
        self.availableCaseTypes = availableCaseTypes;
        self.invitations = ko.observable(invitations.map((invite) => InvitationModel(invite)));
        self.grants = ko.observable(grants.map((grant) => GrantModel(grant)));

        self.removeDomain = function (toRemove){
            console.log(toRemove.domain);
            self.invitations(self.invitations().filter((invite) => {
                return invite.id !== toRemove.id;
            }));
        }
        return self;
    }

    $(function () {
        $("#edit-registry").koApplyBindings(EditModel(
            initialPageData.get("caseTypes"),
            initialPageData.get("availableCaseTypes"),
            initialPageData.get("invitations"),
            initialPageData.get("grants"),
        ));
    });
});
