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

var sumObjects = function(calc, obj) {
    for (var k in obj) {
        if(isNaN(parseInt(obj[k]))) {
            sumObjects(calc[k], obj[k]);
//            sumObjects(calc[k], obj[k]);
        } else
            calc[k] += obj[k];
    }
};


// Pathindia Reduce Helpers
// --------------------------------------------------

var PathIndiaAntenatalStats = function () {
    var self = this;
    self.calc = {
        missed_period: 0,
        confirmed_preg: 0,
        using_contraception: 0,
        registered_preg: 0,
        reg_place: {
            govt: 0,
            priv: 0
        },
        early_registration: 0,
        anc_examination: 0,
        stats: {
            bp: 0,
            weight: 0,
            abdominal_exam: 0,
            hb_exam: 0
        },
        hb: {
            low: 0,
            avg: 0,
            high: 0
        },
        tt_booster: 0,
        ifa_tabs: 0,
        injection_syrup: 0,
        danger_signs: {
            headache: 0,
            blurred_vision: 0,
            edema: 0,
            fetal_mvmt: 0,
            bleeding: 0
        },
        delivery_place: {
            govt: 0,
            priv: 0
        }
    };

    self.rereduce = function (agEntry) {
        sumObjects(self.calc, agEntry);
    };

    self.reduce = function (anc) {
        self.calc.missed_period += anc.missed_period ? 1 : 0;
        self.calc.confirmed_preg += anc.pregnancy_confirmation ? 1 : 0;
        self.calc.using_contraception += anc.using_contraception ? 1 : 0;

        self.calc.registered_preg += anc.pregnancy_registration ? 1 : 0;
        self.calc.reg_place.govt += (anc.pregnancy_registration_place === 'government') ? 1 : 0;
        self.calc.reg_place.priv += (anc.pregnancy_registration_place === 'private') ? 1 : 0;

        if (anc.pregnancy_registration &&
            anc.pregnancy_registration_date &&
            anc.lmp) {
            var lmpDate = new Date(anc.lmp),
                pregRegDate = new Date(anc.pregnancy_registration_date);
            self.calc.early_registration += (Math.abs(pregRegDate.getTime() - lmpDate.getTime()) <= 84*24*60*60*1000) ? 1 : 0;
        }

        self.calc.anc_examination += (anc.is_anc_visit) ? 1 : 0;

        self.calc.stats.bp += anc.most_recent_anc_visit_bp ? 1 : 0;
        self.calc.stats.weight += anc.most_recent_anc_visit_weight ? 1 : 0;
        self.calc.stats.abdominal_exam += anc.most_recent_anc_visit_abdomen ? 1 : 0;
        self.calc.stats.hb_exam += anc.anc_hemoglobin ? 1 : 0;

        self.calc.hb.low += (anc.hemoglobin_value < 7) ? 1 : 0;
        self.calc.hb.avg += (7 <= anc.hemoglobin_value <= 10) ? 1 : 0;
        self.calc.hb.high += (anc.hemoglobin_value > 10) ? 1 : 0;

        self.calc.tt_booster += (anc.tetanus_which_ones === 'tt2' || anc.tetanus_which_ones === 'booster') ? 1 : 0;
        self.calc.ifa_tabs += (anc.how_many_ifa_total > 100) ? 1 : 0;
        self.calc.injection_syrup += (anc.injection_syrup_received) ? 1 : 0;

        self.calc.danger_signs.headache += (anc.anc_headache) ? 1 : 0;
        self.calc.danger_signs.blurred_vision += (anc.anc_blurred_vision) ? 1 : 0;
        self.calc.danger_signs.edema += (anc.anc_edema) ? 1 : 0;
        self.calc.danger_signs.fetal_mvmt += (anc.anc_no_fetal_mvmt) ? 1 : 0;
        self.calc.danger_signs.bleeding += (anc.anc_bleeding) ? 1 : 0;

        self.calc.delivery_place.govt += (anc.delivery_place_determined === ' government_hospital') ? 1 : 0;
        self.calc.delivery_place.priv += (anc.delivery_place_determined === 'private_hospital') ? 1 : 0;
    };

    self.getResult = function () {
        return { antenatal: self.calc };
    };
};

var PathIndiaIntranatalStats = function () {
    var self = this;
    self.calc = {
        outcome: {
            live_birth: 0,
            still_birth: 0,
            abortion: 0
        },
        place: {
            govt: 0,
            priv: 0,
            home: 0
        },
        type: {
            normal: 0,
            lscs: 0,
            forceps: 0
        },
        sex: {
            male: 0,
            female: 0
        },
        weight: {
            low: 0,
            avg: 0,
            high: 0
        }
    };

    self.rereduce = function (agEntry) {
        sumObjects(self.calc, agEntry);
    };

    self.reduce = function (inc) {
        self.calc.outcome.live_birth += (inc.pregnancy_outcome === 'live_birth') ? 1 : 0;
        self.calc.outcome.still_birth += (inc.pregnancy_outcome === 'still_birth') ? 1 : 0;
        self.calc.outcome.abortion += (inc.pregnancy_outcome === 'abortion') ? 1 : 0;

        self.calc.place.govt += (inc.birth_place === 'government_hospital') ? 1 : 0;
        self.calc.place.priv += (inc.birth_place === 'private_hospital') ? 1 : 0;
        self.calc.place.home += (inc.birth_place === 'home') ? 1 : 0;

        self.calc.type.normal += (inc.delivery_type === 'normal') ? 1 : 0;
        self.calc.type.lscs += (inc.delivery_type === 'instrumental') ? 1 : 0;
        self.calc.type.forceps += (inc.delivery_type === 'ceasarean') ? 1 : 0;

        self.calc.sex.male += (inc.child_sex === 'male') ? 1 : 0;
        self.calc.sex.female += (inc.child_sex === 'female') ? 1 : 0;

        self.calc.weight.low += (inc.birth_weight < 2) ? 1 : 0;
        self.calc.weight.avg += (2 <= inc.birth_weight <= 2.5) ? 1 : 0;
        self.calc.weight.high += (inc.birth_weight > 2.5) ? 1 : 0;
    };

    self.getResult = function () {
        return { intranatal: self.calc };
    };
};

var PathIndiaPostnatalStats = function () {
    var self = this;
    self.calc = {
        currently_breastfeeding: 0,
        at_least_one_pnc: 0,
        no_pnc: 0,
        complications: {
            bleeding: 0,
            fever: 0,
            convulsions: 0
        },
        jsy: 0
    };

    self.rereduce = function (agEntry) {
        sumObjects(self.calc, agEntry);
    };

    self.reduce = function (pnc) {
        self.calc.currently_breastfeeding += (pnc.breastfeeding_outcome) ? 1 : 0;
        self.calc.at_least_one_pnc += (pnc.pnc_checkup !== 'no_pnc') ? 1 : 0;
        self.calc.no_pnc += (pnc.pnc_checkup === 'no_pnc') ? 1 : 0;

        self.calc.complications.bleeding += (pnc.pnc_complications === 'bleeding') ? 1 : 0;
        self.calc.complications.fever += (pnc.pnc_complications === 'fever') ? 1 : 0;
        self.calc.complications.convulsions += (pnc.pnc_complications === 'convulsions') ? 1 : 0;

        self.calc.jsy += (pnc.jsy_received) ? 1 : 0;
    };

    self.getResult = function () {
        return { postnatal: self.calc };
    };
};