/* handle xforms */
function get_form_filled_duration(xform_doc) {
    // in milliseconds
    var meta = xform_doc.form.meta;
    if (meta && meta.timeEnd && meta.timeStart)
        return new Date(meta.timeEnd).getTime() - new Date(meta.timeStart).getTime();
    return null;
}

/* HSPH related */

function isHSPHForm(doc) {
    return (doc.doc_type === 'XFormInstance'
            && doc.domain === 'hsph');
}

function isHSPHBirthCase(doc) {
    return (doc.doc_type === 'CommCareCase' && doc.domain === 'hsph' && 
            doc.type === "birth");
}

function isDCOFollowUpReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/E5E03D8D-937D-46C6-AF8F-C1FD176E2E1B");
}

function isCITLReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/0D9CB681-2C07-46AB-8720-66E4FBD94211");
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

function isIHForCHF(doc) {
    return "IHF";
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

function HSPHCaseEntry(doc) {
    var self = this;
    self.doc = doc;
    self.data = {};

    self.getBirthStats = function() {
        self.data.birthEvent = false;
        if (self.doc.mother_delivered_or_referred === 'delivered') {
            self.data.birthEvent = true;
            
        }
    };
}

function HSPHEntry(doc) {
    var self = this;
    self.doc = doc;
    self.form = (doc.form) ? doc.form : doc;
    self.data = {};

    self.getBirthStats = function () {
        self.data.numBirths = 0;
        self.data.birthRegistration = isDCOBirthRegReport(doc);

        if (self.form.mother_delivered_or_referred === "delivered" && self.form.date_delivery) {
            self.data.numBirths = (self.form.multiple_birth === 'yes') ?
                                    parseInt(self.form.multiple_birth_number) : 1;
            self.data.dateBirth = self.form.date_delivery;
        } else if (self.form.case_date_delivery) {
            self.data.numBirths = (self.form.case_multiple_birth === 'yes') ?
                parseInt(self.form.case_multiple_birth_number) : 1;
            self.data.dateBirth = self.form.case_date_delivery;
            self.data.birthDataFromCase = true;
        }

        self.data.referredInBirth = (self.form.referred_in === 'yes');

        self.data.contactProvided = !!(self.form.phone_mother === 'yes' ||
                                        self.form.phone_husband === 'yes' ||
                                        self.form.phone_house === 'yes' ) ||
                                    !!(self.form.phone_mother_number ||
                                        self.form.phone_husband_number ||
                                        self.form.phone_house_number );
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
        self.data.lostToFollowUp = (self.form.follow_up_type === 'lost_to_follow_up');

        if (self.form.meta) {
            var dateAdmitted = (self.form.date_admission) ? new Date(self.form.date_admission) : new Date(self.form.meta.timeEnd);
            var timeEnd = new Date(self.form.meta.timeEnd);
            self.data.openedAt21 = !!(dateAdmitted.getTime() - timeEnd.getTime() >= 21*24*60*60*1000);
        }
    };

    self.getCaseInfo = function () {
        self.data.isClosed = self.form.closed;
        self.data.patientId = self.form.patient_id;
        self.data.visitedDate = self.form.closed_on;
        self.data.followupFormId = self.form.xform_ids[Math.max(0, self.form.xform_ids.length-1)];
        self.data.nameMother = self.form.name_mother;
        self.data.address = self.form.house_address;
        var responseDatespan = calcHSPHBirthDatespan(self.doc);
        self.data.startDate = (responseDatespan) ? responseDatespan.start : self.form.opened_on;
        self.data.endDate = (responseDatespan) ? responseDatespan.end : self.form.opened_on;

        if (self.form.follow_up_type === 'dcc')
            self.data.dccFollowUp = true;
        else if (self.form.follow_up_type === 'dco')
            self.data.dcoFollowUp = true;
    };

    self.getCITLInfo = function () {
        self.data.facilityStatus = (isDCOSiteLogReport(self.doc)) ? -1 : parseInt(self.form.current_implementation_stage);
        self.data.IHFCHF = isIHForCHF(self.doc);

        if (isCITLReport(self.doc)) {
            self.data.isCITLData = true;
            self.data.visitDate = self.form.meta.timeEnd;
        }
    };

    self.getOutcomeStats = function () {
        var follow_up = (self.form.follow_up) ? self.form.follow_up : self.form;

        self.data.maternalDeath = follow_up.maternal_death === 'dead';
        if (! self.data.maternalDeath) {
            self.data.maternalNearMiss = (follow_up.maternal_near_miss === 'yes' ||
                                          // old:
                                            follow_up.icu === 'yes' ||
                                            follow_up.cpr === 'yes' ||
                                            follow_up.fever === 'yes' ||
                                            follow_up.hysterectomy === 'yes' ||
                                            follow_up.transfusion === 'yes' ||
                                            follow_up.fits === 'yes' ||
                                            follow_up.loss_consciousness === 'yes');
        }

        self.data.numStillBirths = 0;
        for (var s=1; s<= 5; s++) {
            var val = follow_up['baby_'+s+'_birth_or_stillbirth'];
            self.data.numStillBirths += (val === 'fresh_stillbirth' || val === 'macerated_stillbirth') ? 1 : 0;
        }

        self.data.numNeonatalMortality = 0;
        for (var b=1; b <= 5; b++) {
            var val = follow_up['baby_'+b+'_death'];
            self.data.numNeonatalMortality += (val === 'dead') ? 1 : 0;
        }

    }
}
