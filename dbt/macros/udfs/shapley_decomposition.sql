{% macro shapley_decomposition() %}

CREATE OR REPLACE FUNCTION {{ target.schema }}.shapley_decomp(
    cur ARRAY<STRUCT<k STRING, v FLOAT64>>,
    pri ARRAY<STRUCT<k STRING, v FLOAT64>>
)
RETURNS STRUCT<shapley STRING, primary_driver STRING, followed_by STRING>
LANGUAGE js AS r"""
  // Exact Shapley for a multiplicative decomposition — port of
  // scripts/ce_buckets/shapley.py (calc_shapley_decomposition).
  const c = {}, p = {};
  (cur || []).forEach(x => { c[x.k] = x.v; });
  (pri || []).forEach(x => { p[x.k] = x.v; });
  const factors = ['traffic','cvr','aov','cr','tr'].filter(
    k => k in c && k in p && c[k] != null && p[k] != null);
  if (factors.length < 2) return { shapley: null, primary_driver: '', followed_by: '' };

  function rev(v) { let r = 1; for (const k of factors) r *= v[k]; return r; }
  function perms(a) {
    if (a.length <= 1) return [a];
    let out = [];
    a.forEach((x, i) => { perms(a.slice(0,i).concat(a.slice(i+1))).forEach(pp => out.push([x].concat(pp))); });
    return out;
  }
  const sh = {}; factors.forEach(k => sh[k] = 0);
  const P = perms(factors);
  P.forEach(perm => {
    let v = {}; factors.forEach(k => v[k] = p[k]);
    let prev = rev(v);
    perm.forEach(f => { v[f] = c[f]; const nr = rev(v); sh[f] += nr - prev; prev = nr; });
  });
  factors.forEach(k => sh[k] /= P.length);
  sh.total = rev(c) - rev(p);

  const label = { traffic: 'traffic', cvr: 'CVR', aov: 'AOV', cr: 'completion', tr: 'take rate' };
  function fmt(k) {
    const x = sh[k]; const arrow = x >= 0 ? '↑' : '↓';
    const a = Math.abs(x);
    const mag = a >= 1000 ? '$' + (a/1000).toFixed(1) + 'K' : '$' + a.toFixed(0);
    return arrow + ' ' + label[k] + ' ' + mag;
  }
  const ranked = factors.slice().sort((x, y) => Math.abs(sh[y]) - Math.abs(sh[x]));
  return {
    shapley: JSON.stringify(sh),
    primary_driver: fmt(ranked[0]),
    followed_by: ranked.length > 1 ? fmt(ranked[1]) : ''
  };
"""

{% endmacro %}
