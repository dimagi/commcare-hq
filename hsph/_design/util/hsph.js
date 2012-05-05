function isHSPHForm(doc) {
    return (doc.doc_type === 'XFormInstance'
            && doc.domain === 'hsph');
}

function isHSPHBirthCase(doc) {
    return (doc.doc_type === 'CommCareCase'
            && doc.domain === 'hsph'
            && doc.type === "birth");
}

function isDCOFollowUpReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/E5E03D8D-937D-46C6-AF8F-C1FD176E2E1B");
}

function isDCOBirthRegReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/FE77C4BD-38EE-499B-AC5E-D7279C83BDB5");
}

function isDCOSiteLogReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/8412C3D0-F06C-49BF-9067-ED62E991F315");
}

function isDCCFollowUpReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/A5B08D8F-139D-46C6-9FDF-B1AD176EAE1F");
}

function getDCO(doc) {
    return doc.form.meta.userID;
}

function getDCTL(doc) {
    return "DCTL Unknown";
}

function calcHSPHBirthDatespan(doc) {
    if (doc.date_delivery || doc.date_admission) {
        var date_del = (doc.date_delivery) ? new Date(doc.date_delivery) : new Date(doc.date_admission);
        return {
            start: new Date(date_del.getTime() + 8*24*60*60*1000),
            end: new Date(date_del.getTime() + 21*24*60*60*1000)
        };
    }
    return null;
}

function HSPHEntry(doc) {
    var self = this;
    self.doc = doc;
    self.form = (doc.form) ? doc.form : doc;
    self.data = {};

    self.getBirthStats = function () {
        self.data.numBirths = 0;
        if (self.form.mother_delivered_or_referred === "delivered") {
            self.data.numBirths = (self.form.multiple_birth === 'yes') ?
                                    parseInt(self.form.multiple_birth_number) : 1;
            self.data.dateBirth = self.form.date_delivery;
        } else if (self.form.case_date_delivery) {
            self.data.numBirths = (self.form.case_multiple_birth === 'yes') ?
                parseInt(self.form.case_multiple_birth_number) : 1;
            self.data.dateBirth = self.form.case_date_delivery;
            self.data.birthDataFromCase = true;
        }

        self.data.contactProvided = !!(self.form.phone_mother === 'yes' ||
                                        self.form.phone_husband === 'yes' ||
                                        self.form.phone_house === 'yes' );
    };

    self.getSiteInfo = function () {
        self.data.siteId = (self.form.site_id) ? self.form.site_id : "unknown";
        if (isDCOSiteLogReport(self.doc)) {
            self.data.siteVisit = true;
            self.data.visitDate = self.form.meta.timeEnd;
        }
        self.data.region = self.form.region_id;
        self.data.district = self.form.district_id;
        self.data.siteNum = self.form.site_number;
    };

    self.getFormLengthInfo = function () {
        self.data.registrationLength = get_form_filled_duration(self.doc);
    };

    self.getFollowUpStatus = function () {
        if (isDCOFollowUpReport(self.doc))
            self.data.homeVisit = true;
        if (isDCCFollowUpReport(self.doc))
            self.data.callCenterCall = true;

        self.data.followupComplete = self.form.result_follow_up === "1";
        self.data.followupTransferred = self.form.result_field_management === "1";
        self.data.followupWaitlisted = self.form.result_wait_list === "1";
        if (self.form.meta) {
            var dateAdmitted = (self.form.date_admission) ? new Date(self.form.date_admission) : new Date(self.form.meta.timeEnd);
            var timeEnd = new Date(self.form.meta.timeEnd);
            self.data.openedAt21 = !!(dateAdmitted.getTime() - timeEnd.getTime() >= 21*24*60*60*1000);
        }
    };

    self.getDCCFollowUpStats = function () {
        var followUpDate = new Date(self.form.meta.timeEnd),
            birthDate = new Date(self.form)
    };

    self.getCaseInfo = function () {
        self.data.isClosed = self.form.closed;
        self.data.patientId = self.form.patient_id;
        self.data.visitedDate = self.form.closed_on;
        self.data.followupFormId = self.form.xform_ids[Math.max(0, self.form.xform_ids.length-1)];
        self.data.nameMother = self.form.name_mother;
        self.data.address = self.form.house_address;
        var responseDatespan = calcHSPHBirthDatespan(self.doc);
        self.data.startDate = (responseDatespan) ? responseDatespan.start : self.form.doc.opened_on;
        self.data.endDate = (responseDatespan) ? responseDatespan.end : self.form.doc.opened_on;

        if (self.form.follow_up_type === 'dcc')
            self.data.dccFollowUp = true;
        else if (self.form.follow_up_type === 'dco')
            self.data.dcoFollowUp = true;
    }
}