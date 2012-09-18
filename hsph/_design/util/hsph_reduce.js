// Underscore.js snippets
// -----------------------------------
ArrayProto = Array.prototype;
var slice  = ArrayProto.slice,
    nativeForEach = ArrayProto.forEach,
    breaker = {};

// The cornerstone, an `each` implementation, aka `forEach`.
// Handles objects with the built-in `forEach`, arrays, and raw objects.
// Delegates to **ECMAScript 5**'s native `forEach` if available.
var each = function(obj, iterator, context) {
    if (obj == null) return;
    if (nativeForEach && obj.forEach === nativeForEach) {
        obj.forEach(iterator, context);
    } else if (obj.length === +obj.length) {
        for (var i = 0, l = obj.length; i < l; i++) {
            if (i in obj && iterator.call(context, obj[i], i, obj) === breaker) return;
        }
    } else {
        for (var key in obj) {
            if (_.has(obj, key)) {
                if (iterator.call(context, obj[key], key, obj) === breaker) return;
            }
        }
    }
};


// Extend a given object with all the properties in passed-in object(s).
var extend = function(obj) {
    each(slice.call(arguments, 1), function(source) {
        for (var prop in source) {
            obj[prop] = source[prop];
        }
    });
    return obj;
};


// HSPH Reduce Helpers
// ---------------------------------------

var HSPHLengthStats = function () {
    var self = this;
    self.calc = {
        totalRegistrations: 0,
        totalRegistrationTime: 0,
        averageRegistrationLength: 0
    };

    self.rereduce = function (agEntry) {
        if (agEntry.averageRegistrationLength) {
            self.calc.totalRegistrationTime += agEntry.totalRegistrationTime;
            self.calc.totalRegistrations += 1;
        }
    };

    self.reduce = function (curEntry) {
        self.calc.totalRegistrationTime += curEntry.registrationLength;
        self.calc.totalRegistrations ++;
    };

    self.getResult = function () {
        self.calc.averageRegistrationLength = (self.calc.totalRegistrationTime > 0) ? Math.round(self.calc.totalRegistrationTime/self.calc.totalRegistrations) : null;
        return self.calc;
    };
};

var HSPHBirthCounter = function () {
    var self = this;
    self.calc = {
        totalBirths: 0,
        totalBirthsWithoutContact: 0,
        totalBirthsWithContact: 0,
        totalBirthEvents: 0,
        totalBirthRegistrationEvents: 0,
        totalBirthEventsOnRegistration: 0,
        totalReferredInBirths: 0
    };

    self.rereduce = function (agEntry) {
        self.calc.totalBirths += agEntry.totalBirths;
        self.calc.totalBirthEvents += agEntry.totalBirthEvents;
        self.calc.totalBirthRegistrationEvents += agEntry.totalBirthRegistrationEvents;
        self.calc.totalBirthsWithoutContact += agEntry.totalBirthsWithoutContact;
        self.calc.totalBirthsWithContact += agEntry.totalBirthsWithContact;
        self.calc.totalBirthEventsOnRegistration += agEntry.totalBirthEventsOnRegistration;
        self.calc.totalReferredInBirths += agEntry.totalReferredInBirths;
    };

    self.reduce = function (curEntry) {
        self.calc.totalBirths += curEntry.numBirths;
        self.calc.totalBirthEvents += (curEntry.numBirths > 0) ? 1 : 0;
        self.calc.totalBirthEventsOnRegistration += (curEntry.birthRegistration && (curEntry.numBirths > 0)) ? 1 : 0;
        self.calc.totalBirthRegistrationEvents += (curEntry.birthRegistration) ? 1 : 0;
        self.calc.totalReferredInBirths += (curEntry.referredInBirth) ? 1 : 0;
        if (curEntry.contactProvided)
            self.calc.totalBirthsWithContact += curEntry.numBirths;
        else
            self.calc.totalBirthsWithoutContact += curEntry.numBirths;
    };

    self.getResult = function () {
        return self.calc;
    }
};

var HSPHSiteVisitStats = function (onlyTotals) {
    var self = this;
    self.calc = {
        numFacilityVisits: 0
    };

    self.onlyTotals = (onlyTotals === true);
    if (!self.onlyTotals) {
        self.calc.siteVisitStats = {};
        self.calc.numFacilitiesVisited = 0;
        self.calc.lessThanTwoWeeklyFacilityVisits = 0;
    }

    self.rereduce = function (agEntry) {
        if(self.onlyTotals) {
            self.calc.numFacilityVisits += agEntry.numFacilityVisits;
        } else
            for (var site in agEntry.siteVisitStats) {
                if (self.calc.siteVisitStats[site]) {
                    self.calc.siteVisitStats[site].visits += agEntry.siteVisitStats[site].visits;
                } else {
                    self.calc.siteVisitStats[site] = {};
                    self.calc.siteVisitStats[site].visits = agEntry.siteVisitStats[site].visits;
                    self.calc.siteVisitStats[site].dates = new Array();
                }
                self.calc.siteVisitStats[site].dates = self.calc.siteVisitStats[site].dates.concat(agEntry.siteVisitStats[site].dates);
            }
    };

    self.reduce = function (curEntry) {
        if(self.onlyTotals && curEntry.siteVisit) {
            self.calc.numFacilityVisits += 1;
        } else if (self.calc.siteVisitStats) {
            var siteID = curEntry.siteId;
            if (self.calc.siteVisitStats[siteID]) {
                self.calc.siteVisitStats[siteID].visits += 1;
            } else {
                self.calc.siteVisitStats[siteID] = {};
                self.calc.siteVisitStats[siteID].visits = 1;
                self.calc.siteVisitStats[siteID].dates = new Array();
            }
            self.calc.siteVisitStats[siteID].dates.push(curEntry.visitDate);
        }
    };

    self.getResult = function () {
        if (!self.onlyTotals) {
            for (var s in self.calc.siteVisitStats) {
                var visitDates = self.calc.siteVisitStats[s].dates,
                    twoVisitsInAWeek = false;
                for (var a in visitDates) {
                    for (var b in visitDates) {
                        if (a != b) {
                            var firstVisit = new Date(a),
                                secondVisit = new Date(b),
                                millisecondsInWeek = 7*24*60*60*1000,
                                millisecondsInDay = 24*60*60*1000;
                            if ((firstVisit.getTime() - secondVisit.getTime() <= millisecondsInWeek)
                                && (firstVisit.getTime() - secondVisit.getTime() > millisecondsInDay) ) {
                                twoVisitsInAWeek = true;
                            }
                        }
                    }
                }
                if (!twoVisitsInAWeek)
                    self.calc.lessThanTwoWeeklyFacilityVisits += 1;

                self.calc.numFacilityVisits += self.calc.siteVisitStats[s].visits;
                self.calc.numFacilitiesVisited += 1;
            }
        }
        return self.calc;
    };
};

var HSPHHomeVisitStats = function () {
    var self = this;
    self.calc = {
        numHomeVisits: 0,
        numHomeVisitsCompleted: 0,
        numHomeVisitsOpenAt21: 0
    };

    self.rereduce = function (agEntry) {
        if (agEntry && agEntry.numHomeVisits) {
            self.calc.numHomeVisits += agEntry.numHomeVisits;
            self.calc.numHomeVisitsCompleted += agEntry.numHomeVisitsCompleted;
            self.calc.numHomeVisitsOpenAt21 += agEntry.numHomeVisitsOpenAt21;
        }
    };

    self.reduce = function (curEntry) {
        if (curEntry && curEntry.homeVisit) {
            self.calc.numHomeVisits += 1;
            self.calc.numHomeVisitsCompleted += (curEntry.followupComplete) ? 1 : 0;
            self.calc.numHomeVisitsOpenAt21 += (curEntry.openedAt21) ? 1 : 0;
        }
    };

    self.getResult = function () {
        return self.calc;
    };
};

var HSPHDCCFollowupStats = function () {
    var self = this;
    self.calc = {
        numCallsComplete: 0,
        numBirthsFollowedUp: 0,
        numCallsWaitlisted: 0,
        numCallsTransferred: 0,
        numBirthsTransferred: 0,
        numOtherEvents: 0
    };

    self.rereduce = function (agEntry) {
        self.calc.numCallsComplete += agEntry.numCallsComplete;
        self.calc.numBirthsFollowedUp += agEntry.numBirthsFollowedUp;
        self.calc.numCallsTransferred += agEntry.numCallsTransferred;
        self.calc.numBirthsTransferred += agEntry.numBirthsTransferred;
        self.calc.numCallsWaitlisted += agEntry.numCallsWaitlisted;
        self.calc.numOtherEvents += agEntry.numOtherEvents;
    };

    self.reduce = function (curEntry) {
        if (curEntry.followupComplete) {
            self.calc.numCallsComplete += 1;
            self.calc.numBirthsFollowedUp += (curEntry.numBirths) ? curEntry.numBirths : 0;
        } else if (curEntry.followupTransferred) {
            self.calc.numCallsTransferred += 1;
            self.calc.numBirthsTransferred += (curEntry.numBirths) ? curEntry.numBirths : 0;
        } else if (curEntry.followupWaitlisted)
            self.calc.numCallsWaitlisted += 1;
        else
            self.calc.numOtherEvents += 1;
    };

    self.getResult = function () {
        return self.calc;
    };
};

var HSPHOutcomesCounter = function () {
    var self = this;
    var stats = {
        maternalDeaths: 0,
        maternalNearMisses: 0,
        stillBirthEvents: 0,
        neonatalMortalityEvents: 0,
        positiveOutcomes: 0,
        positiveOutcomeEvents: 0,
        liveBirthEvents: 0,
        lostToFollowUp: 0,
        followedUp: 0,
        combinedMortalityOutcomes: 0
    };

    self.calc = extend({}, stats);
    self.calc.atDischarge = extend({}, stats);
    self.calc.on7Days = extend({}, stats);

    self.rereduce = function (agEntry) {
        for (var key in stats)  {
            self.calc[key] += agEntry[key];
            self.calc.atDischarge[key] += agEntry.atDischarge[key];
            self.calc.on7Days[key] += agEntry.on7Days[key];
        }
    };

    self.reduce = function (curEntry) {
        stats.maternalDeaths = (curEntry.maternalDeath) ? 1 : 0;
        stats.maternalNearMisses = (curEntry.maternalNearMiss) ? 1 : 0;
        stats.stillBirthEvents = (curEntry.numStillBirths > 0) ? 1 : 0;
        stats.neonatalMortalityEvents = (curEntry.numNeonatalMortality > 0) ? 1 : 0;
        stats.positiveOutcomes = (stats.maternalDeaths + stats.maternalNearMisses +
                                  stats.stillBirthEvents + stats.neonatalMortalityEvents);
        stats.positiveOutcomeEvents = stats.positiveOutcomes > 0 ? 1 : 0;
        stats.combinedMortalityOutcomes = stats.maternalDeaths + stats.stillBirthEvents + stats.neonatalMortalityEvents;
        stats.liveBirthEvents = (curEntry.numBirths > curEntry.numStillBirths) ? 1 : 0;
        
        stats.lostToFollowUp = (curEntry.lostToFollowUp) ? 1 : 0;
        stats.followedUp = (curEntry.followupComplete) ? 1 : 0;

        for (var key in stats) {
            if (curEntry.outcomeOnDischarge)
                self.calc.atDischarge[key] += stats[key];
            else if (curEntry.outcomeOn7Days)
                self.calc.on7Days[key] += stats[key];
            self.calc[key] += stats[key];
        }
    };

    self.getResult = function () {
        return self.calc;
    };
};

var HSPHFacilityStatusStats = function () {
    var self = this;
    self.calc = {
        facilityStatuses: new Array([],[],[],[])
    };

    function addSite(siteList, siteID) {
        if (siteList.indexOf(siteID) < 0)
            siteList.push(siteID);
    }

    function removeSite(siteList, siteID) {
        var ind = siteList.indexOf(siteID);
        if (ind >= 0)
            delete siteList.splice(ind,1);
    }

    self.rereduce = function (agEntry) {
        for (var ag in agEntry.facilityStatuses) {
            for (var s in agEntry.facilityStatuses[ag]) {
                addSite(self.calc.facilityStatuses[ag], agEntry.facilityStatuses[ag][s]);
            }
        }
    };

    self.reduce = function (curEntry) {
        if ( (-1 <= curEntry.facilityStatus <= 2) && curEntry.siteId) {
            addSite(self.calc.facilityStatuses[curEntry.facilityStatus+1], curEntry.siteId);
        }
    };

    self.getResult = function () {
        for (var a=3; a >=0; a--) {
            for (var site in self.calc.facilityStatuses[a])
                for (var b=a-1; b >= 0; b--)
                    removeSite(self.calc.facilityStatuses[b], self.calc.facilityStatuses[a][site]);
        }

        self.calc.numAtZero = self.calc.facilityStatuses[0].length;
        self.calc.numSBR = self.calc.facilityStatuses[1].length;
        self.calc.numBaseline = self.calc.facilityStatuses[2].length;
        self.calc.numTrial = self.calc.facilityStatuses[3].length;

        return self.calc;

    };
};

