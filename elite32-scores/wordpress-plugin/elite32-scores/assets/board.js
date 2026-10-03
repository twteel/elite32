/* Elite32 Scores — public scoreboard for the [elite32_scores] shortcode. */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function when(iso) {
    if (!iso) return 'Time TBA';
    return new Date(iso).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  function statusLabel(g) {
    if (g.status === 'live') return 'LIVE' + (g.period ? ' · ' + g.period : '');
    if (g.status === 'final') return 'FINAL' + (g.period && /OT/i.test(g.period) ? '/' + g.period : '');
    if (g.status === 'scheduled') return when(g.starts_at);
    return g.status.toUpperCase();
  }

  function team(g, side) {
    var other = side === 'home' ? 'away' : 'home';
    var won = g.status === 'final' && g[side + '_score'] > g[other + '_score'];
    var showScore = g.status !== 'scheduled';
    return '<div class="e32b-team' + (won ? ' is-winner' : '') + '"><span>' + esc(g[side + '_team']) + '</span>' +
      '<strong>' + (showScore ? g[side + '_score'] : '') + '</strong></div>';
  }

  function render(el, games) {
    if (!games.length) {
      el.innerHTML = '<p class="e32b-empty">No games right now. Check back soon.</p>';
      return;
    }
    var order = { live: 0, scheduled: 1, final: 2 };
    games = games.slice().sort(function (a, b) {
      return (order[a.status] == null ? 3 : order[a.status]) - (order[b.status] == null ? 3 : order[b.status]);
    });
    el.innerHTML = '<div class="e32b-grid">' + games.map(function (g) {
      return '<article class="e32b-game is-' + esc(g.status) + '">' +
        '<header><span class="e32b-badge">' + esc(statusLabel(g)) + '</span>' +
        '<span class="e32b-meta">' + esc([g.event_name, g.division].filter(Boolean).join(' · ')) + '</span></header>' +
        team(g, 'away') + team(g, 'home') +
        (g.venue ? '<footer>' + esc(g.venue) + '</footer>' : '') +
        '</article>';
    }).join('') + '</div>';
  }

  function start(el) {
    var src = el.getAttribute('data-src');
    var every = parseInt(el.getAttribute('data-refresh'), 10) * 1000;
    function tick() {
      if (document.hidden) return;
      var url = src + (src.indexOf('?') < 0 ? '?' : '&') + '_=' + Date.now();
      fetch(url, { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (data) { render(el, data.games || []); })
        .catch(function () { /* keep showing the last scores */ });
    }
    tick();
    setInterval(tick, every);
    document.addEventListener('visibilitychange', tick);
  }

  document.querySelectorAll('.e32b[data-src]').forEach(start);
})();
