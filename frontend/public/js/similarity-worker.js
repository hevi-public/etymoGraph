/**
 * Web Worker: pairwise phonetic similarity using Dolgopolsky consonant classes.
 *
 * Receives an array of words (each with id, dolgo_consonants, dolgo_first2)
 * and a similarity threshold. Posts back all edges above the threshold.
 * Runs off the main thread so the UI stays responsive.
 */

function levenshteinDistance(s1, s2) {
    if (!s1 && !s2) return 0.0;
    if (!s1 || !s2) return 1.0;

    var n = s1.length;
    var m = s2.length;
    var prev = new Array(m + 1);
    var curr = new Array(m + 1);

    for (var j = 0; j <= m; j++) prev[j] = j;

    for (var i = 1; i <= n; i++) {
        curr[0] = i;
        for (j = 1; j <= m; j++) {
            var cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
            curr[j] = Math.min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost
            );
        }
        var tmp = prev;
        prev = curr;
        curr = tmp;
    }

    var maxLen = Math.max(n, m);
    return maxLen > 0 ? prev[m] / maxLen : 0.0;
}

function sharedPrefix(s1, s2) {
    var len = Math.min(s1.length, s2.length);
    var i = 0;
    while (i < len && s1[i] === s2[i]) i++;
    return s1.slice(0, i);
}

self.onmessage = function (e) {
    var words = e.data.words;
    var threshold = e.data.threshold;
    var edges = [];

    for (var i = 0; i < words.length; i++) {
        var ccI = words[i].dolgo_consonants;
        var f2I = words[i].dolgo_first2;
        var idI = words[i].id;

        if (!ccI) continue;

        for (var j = i + 1; j < words.length; j++) {
            var ccJ = words[j].dolgo_consonants;
            var f2J = words[j].dolgo_first2;

            if (!ccJ) continue;

            var sim = 1.0 - levenshteinDistance(ccI, ccJ);
            var turchin = f2I.length >= 2 && f2J.length >= 2 && f2I === f2J;

            if (sim >= threshold || turchin) {
                edges.push({
                    source: idI,
                    target: words[j].id,
                    similarity: Math.round(sim * 1000) / 1000,
                    turchin_match: turchin,
                    shared_classes: sharedPrefix(ccI, ccJ),
                });
            }
        }
    }

    self.postMessage({ edges: edges });
};
