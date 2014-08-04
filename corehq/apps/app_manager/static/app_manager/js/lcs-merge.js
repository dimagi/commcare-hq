/*
    Adapted from the algorithms presented on
    http://en.wikipedia.org/wiki/Longest_common_subsequence_problem

    lcsMerge returns the "unified diff" of two sequences.
    If you read off [item.token for item in lcsMerge(X, Y) if item.x]
    you should get back X. (And analogously for Y.)
 */
function lcsMerge(X, Y, isEqual) {
    'use strict';
    isEqual = isEqual || function (a, b) {
        return a === b;
    };
    var cache = {};
    cache.get = function (i, j) {
        var cache_key = i + ' ' + j;
        var val = cache[cache_key];
        if (val) {
            return {
                lcs_length: val.lcs_length,
                merge: val.merge.slice(0)
            };
        } else {
            return null;
        }
    };
    cache.set = function (i, j, val) {
        var cache_key = i + ' ' + j;
        cache[cache_key] = val;
    };
    function recLcsMerge(i, j) {
        var val, val1, val2, recur = recLcsMerge;
        val = cache.get(i, j);
        if (val) {
            return val;
        }
        if (i === 0 && j === 0) {
            val = {
                lcs_length: 0,
                merge: []
            };
        } else if (i === 0) {
            val = recur(i, j - 1);
            val.merge.push({x: false, y: true, token: Y[j - 1]});
        } else if (j === 0) {
            val = recur(i - 1, j);
            val.merge.push({x: true, y: false, token: X[i - 1]});
        } else if (isEqual(X[i - 1], Y[j - 1])) {
            val = recur(i - 1, j - 1);
            val.lcs_length++;
            val.merge.push({x: true, y: true, token: X[i - 1]});
        } else {
            val1 = recur(i, j - 1);
            val2 = recur(i - 1, j);
            if (val2.lcs_length > val1.lcs_length) {
                val = val2;
                val.merge.push({x: true, y: false, token: X[i - 1]});
            } else {
                val = val1;
                val.merge.push({x: false, y: true, token: Y[j - 1]});
            }
        }
        cache.set(i, j, val);
        return cache.get(i, j);
    }

    return recLcsMerge(X.length, Y.length).merge;
}
