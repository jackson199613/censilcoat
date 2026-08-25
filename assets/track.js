/*!
 * Censilcoat — click attribution capture
 * assets/track.js
 *
 * Captures Google Ads click IDs and UTM parameters on the visitor's FIRST
 * landing, stores them for 90 days, and stamps them into the hidden fields of
 * the sample-request / document-request forms on submit.
 *
 * Why first-touch persistence: a visitor typically lands from an ad on /
 * or a product page, browses, and only fills the form later on /contact.
 * By then the URL no longer carries ?gclid=..., so reading the query string
 * at form time would always come up empty. We stash it on arrival instead.
 *
 * No dependencies. Safe to load with `defer`.
 */
(function () {
  'use strict';

  var STORE_KEY = 'censil_attr';
  var TTL_DAYS = 90;

  // Google click IDs. gclid = standard, gbraid/wbraid = iOS / app-to-web.
  var CLICK_IDS = ['gclid', 'gbraid', 'wbraid'];
  var UTMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

  // ---------- storage helpers (never throw: Safari private mode, ITP, etc.) ----

  function readStore() {
    try {
      var raw = window.localStorage.getItem(STORE_KEY);
      if (!raw) return null;
      var data = JSON.parse(raw);
      if (!data || !data.exp || Date.now() > data.exp) {
        window.localStorage.removeItem(STORE_KEY);
        return null;
      }
      return data;
    } catch (e) {
      return null;
    }
  }

  function writeStore(data) {
    try {
      data.exp = Date.now() + TTL_DAYS * 24 * 60 * 60 * 1000;
      window.localStorage.setItem(STORE_KEY, JSON.stringify(data));
    } catch (e) {
      /* storage unavailable — attribution degrades to same-page-load only */
    }
  }

  // ---------- capture ---------------------------------------------------------

  function currentParams() {
    var out = {};
    try {
      var qs = new URLSearchParams(window.location.search);
      CLICK_IDS.concat(UTMS).forEach(function (k) {
        var v = qs.get(k);
        if (v) out[k] = v.slice(0, 512);
      });
    } catch (e) {
      /* very old browser — skip */
    }
    return out;
  }

  function capture() {
    var fresh = currentParams();
    var stored = readStore();

    var hasFreshClick = CLICK_IDS.some(function (k) { return fresh[k]; });
    var hasFreshUtm = UTMS.some(function (k) { return fresh[k]; });

    // A new ad click (or a new UTM-tagged visit) overwrites the old attribution
    // — last paid touch wins, which matches how Google Ads itself attributes.
    if (hasFreshClick || hasFreshUtm) {
      var data = {
        landing_page: window.location.origin + window.location.pathname,
        referrer: (document.referrer || '').slice(0, 512),
        ts: new Date().toISOString()
      };
      CLICK_IDS.concat(UTMS).forEach(function (k) {
        if (fresh[k]) data[k] = fresh[k];
      });
      writeStore(data);
      return data;
    }

    // No new campaign params. Keep whatever we already had.
    if (stored) return stored;

    // First ever visit, untagged (organic / direct). Still worth recording so
    // we can tell "organic lead" apart from "attribution broken".
    var organic = {
      landing_page: window.location.origin + window.location.pathname,
      referrer: (document.referrer || '').slice(0, 512),
      ts: new Date().toISOString()
    };
    writeStore(organic);
    return organic;
  }

  // ---------- stamp into forms ------------------------------------------------

  function setField(form, name, value) {
    if (value === undefined || value === null || value === '') return;
    var el = form.querySelector('[name="' + name + '"]');
    if (el) {
      el.value = value;
      return;
    }
    // Field isn't in the markup — add it so nothing is silently dropped.
    // NOTE: Netlify registers form fields by scanning the deployed HTML, so a
    // field injected at runtime will be submitted but may not appear as a
    // column in the Netlify UI until it also exists in the static markup.
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }

  function stamp(attr) {
    var forms = document.querySelectorAll('form[name="sample-request"], form[name="document-request"]');
    Array.prototype.forEach.call(forms, function (form) {
      CLICK_IDS.concat(UTMS).forEach(function (k) {
        setField(form, k, attr[k]);
      });
      setField(form, 'landing_page', attr.landing_page);
      setField(form, 'ad_referrer', attr.referrer);
      setField(form, 'first_seen', attr.ts);
      setField(form, 'submitted_page', window.location.origin + window.location.pathname);
    });
  }

  // ---------- boot ------------------------------------------------------------

  function init() {
    var attr = capture();
    stamp(attr);
    // Expose for debugging: open the console and type censilAttr()
    window.censilAttr = function () { return attr; };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
