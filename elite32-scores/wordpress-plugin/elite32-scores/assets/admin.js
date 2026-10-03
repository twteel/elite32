/* Elite32 Scores — wp-admin scorekeeper screen. Talks to /wp-json/elite32/v1. */
(function () {
  'use strict';

  var cfg = window.E32Scores;
  var $ = function (id) { return document.getElementById(id); };
  var gamesEl = $('e32a-games');
  var statusEl = $('e32a-status');
  var dateEl = $('e32a-date');
  var allEl = $('e32a-all');
  var games = [];
  var openEdits = {}; // game id -> true while its edit form is expanded

  // path may carry its own query string; cfg.root may already have one (?rest_route=... on plain permalinks).
  function url(path) {
    var q = path.indexOf('?');
    var route = q < 0 ? path : path.slice(0, q);
    var query = q < 0 ? '' : path.slice(q + 1);
    var base = cfg.root.replace(/\/$/, '') + route;
    return query ? base + (base.indexOf('?') < 0 ? '?' : '&') + query : base;
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(url(path), {
      method: opts.method || 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'X-WP-Nonce': cfg.nonce, 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data && data.message ? data.message : 'Request failed (' + res.status + ')');
        return data;
      });
    });
  }

  function flash(msg, isError) {
    statusEl.textContent = msg;
    statusEl.className = 'e32a-status' + (isError ? ' is-error' : '');
    if (!isError) setTimeout(function () { if (statusEl.textContent === msg) statusEl.textContent = ''; }, 2500);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ISO UTC -> "YYYY-MM-DDTHH:MM" in the site's time zone (for datetime-local inputs).
  function toSiteLocal(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    var parts;
    try {
      parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: cfg.timezone, year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
      }).formatToParts(d);
    } catch (e) {
      parts = new Intl.DateTimeFormat('en-CA', {
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
      }).formatToParts(d);
    }
    var p = {};
    parts.forEach(function (x) { p[x.type] = x.value; });
    return p.year + '-' + p.month + '-' + p.day + 'T' + p.hour + ':' + p.minute;
  }

  function timeLabel(iso) {
    if (!iso) return 'Time TBA';
    return toSiteLocal(iso).replace('T', ' ');
  }

  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function load() {
    var q = allEl.checked ? '?all=1' : '?date=' + encodeURIComponent(dateEl.value || today());
    return api('/games' + q + '&_=' + Date.now()).then(function (data) {
      games = data.games;
      render();
      var events = {};
      games.forEach(function (g) { if (g.event_name) events[g.event_name] = true; });
      $('e32a-events').innerHTML = Object.keys(events).map(function (e) {
        return '<option value="' + esc(e) + '">';
      }).join('');
    }).catch(function (e) { flash(e.message, true); });
  }

  function scoreButtons(g, side) {
    return [-1, 1, 2, 3].map(function (n) {
      return '<button type="button" class="e32a-pt' + (n < 0 ? ' is-minus' : '') + '" data-act="pts" data-id="' + g.id +
        '" data-side="' + side + '" data-n="' + n + '">' + (n > 0 ? '+' + n : n) + '</button>';
    }).join('');
  }

  function render() {
    if (!games.length) {
      gamesEl.innerHTML = '<p class="e32a-empty">No games for this day yet. Add one below, or tick “Show all days”.</p>';
      return;
    }
    gamesEl.innerHTML = games.map(function (g) {
      var statusOpts = cfg.statuses.map(function (s) {
        return '<option value="' + s + '"' + (s === g.status ? ' selected' : '') + '>' + s + '</option>';
      }).join('');
      return '' +
        '<article class="e32a-game is-' + esc(g.status) + '" data-id="' + g.id + '">' +
          '<header class="e32a-game__head">' +
            '<span class="e32a-badge">' + esc(g.status) + (g.period ? ' · ' + esc(g.period) : '') + '</span>' +
            '<span class="e32a-meta">' + esc([g.event_name, g.division, g.venue].filter(Boolean).join(' · ')) + '</span>' +
            '<span class="e32a-meta">' + esc(timeLabel(g.starts_at)) + '</span>' +
          '</header>' +
          ['away', 'home'].map(function (side) {
            return '<div class="e32a-row">' +
              '<span class="e32a-team">' + esc(g[side + '_team']) + ' <small>' + side + '</small></span>' +
              '<span class="e32a-score">' + g[side + '_score'] + '</span>' +
              '<span class="e32a-pts">' + scoreButtons(g, side) + '</span>' +
            '</div>';
          }).join('') +
          '<div class="e32a-controls">' +
            '<select data-act="status" data-id="' + g.id + '">' + statusOpts + '</select>' +
            '<input data-act="period" data-id="' + g.id + '" value="' + esc(g.period) + '" placeholder="Period (Q1, 2nd Half, OT)">' +
            '<button type="button" class="button" data-act="edit" data-id="' + g.id + '">Edit</button>' +
            '<button type="button" class="button-link e32a-del" data-act="delete" data-id="' + g.id + '">Delete</button>' +
          '</div>' +
          '<form class="e32a-form e32a-edit" data-id="' + g.id + '"' + (openEdits[g.id] ? '' : ' hidden') + '>' +
            field('Event', 'event_name', g.event_name) +
            field('Division', 'division', g.division) +
            field('Court / venue', 'venue', g.venue) +
            '<label>Start <input type="datetime-local" name="starts_at" value="' + esc(toSiteLocal(g.starts_at)) + '"></label>' +
            field('Home team', 'home_team', g.home_team) +
            field('Away team', 'away_team', g.away_team) +
            field('Home score', 'home_score', g.home_score, 'number') +
            field('Away score', 'away_score', g.away_score, 'number') +
            '<button class="button button-primary" type="submit">Save</button>' +
          '</form>' +
        '</article>';
    }).join('');
  }

  function field(label, name, value, type) {
    return '<label>' + label + ' <input type="' + (type || 'text') + '" name="' + name + '" value="' + esc(value) + '"></label>';
  }

  function replaceGame(updated) {
    games = games.map(function (g) { return g.id === updated.id ? updated : g; });
    render();
  }

  function formData(form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (el.name) out[el.name] = el.value;
    });
    return out;
  }

  gamesEl.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-act]');
    if (!btn || btn.tagName === 'SELECT' || btn.tagName === 'INPUT') return;
    var id = btn.getAttribute('data-id');
    var act = btn.getAttribute('data-act');

    if (act === 'pts') {
      btn.disabled = true;
      api('/games/' + id + '/points', {
        method: 'POST',
        body: { side: btn.getAttribute('data-side'), points: parseInt(btn.getAttribute('data-n'), 10) }
      }).then(function (g) { replaceGame(g); flash('Saved'); })
        .catch(function (err) { btn.disabled = false; flash(err.message, true); });
    } else if (act === 'edit') {
      var f = gamesEl.querySelector('form[data-id="' + id + '"]');
      f.hidden = !f.hidden;
      openEdits[id] = !f.hidden;
    } else if (act === 'delete') {
      if (!confirm('Delete this game?')) return;
      api('/games/' + id, { method: 'DELETE' }).then(function () { flash('Deleted'); load(); })
        .catch(function (err) { flash(err.message, true); });
    }
  });

  gamesEl.addEventListener('change', function (e) {
    var el = e.target;
    var act = el.getAttribute('data-act');
    if (act !== 'status' && act !== 'period') return;
    var body = {};
    body[act] = el.value;
    api('/games/' + el.getAttribute('data-id'), { method: 'PATCH', body: body })
      .then(function (g) { replaceGame(g); flash('Saved'); })
      .catch(function (err) { flash(err.message, true); });
  });

  gamesEl.addEventListener('submit', function (e) {
    e.preventDefault();
    var form = e.target;
    api('/games/' + form.getAttribute('data-id'), { method: 'PATCH', body: formData(form) })
      .then(function (g) { delete openEdits[g.id]; replaceGame(g); flash('Saved'); })
      .catch(function (err) { flash(err.message, true); });
  });

  $('e32a-add-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var form = e.target;
    api('/games', { method: 'POST', body: formData(form) }).then(function (g) {
      flash('Game added');
      ['home_team', 'away_team'].forEach(function (n) { form.elements[n].value = ''; });
      if (g.starts_at && !allEl.checked) dateEl.value = toSiteLocal(g.starts_at).slice(0, 10);
      load();
    }).catch(function (err) { flash(err.message, true); });
  });

  $('e32a-bulk-go').addEventListener('click', function () {
    var lines = $('e32a-bulk').value.split('\n').map(function (l) { return l.trim(); }).filter(Boolean);
    if (!lines.length) return;
    var done = 0;
    var failed = [];
    var chain = Promise.resolve();
    lines.forEach(function (line, i) {
      var p = line.split('|').map(function (s) { return s.trim(); });
      chain = chain.then(function () {
        return api('/games', {
          method: 'POST',
          body: { starts_at: p[0], event_name: p[1], division: p[2], venue: p[3], home_team: p[4], away_team: p[5] }
        }).then(function () { done++; }, function (err) { failed.push('Line ' + (i + 1) + ': ' + err.message); });
      });
    });
    chain.then(function () {
      if (failed.length) {
        flash(done + ' imported. ' + failed.join(' '), true);
      } else {
        flash(done + ' games imported');
        $('e32a-bulk').value = '';
      }
      load();
    });
  });

  dateEl.value = today();
  dateEl.addEventListener('change', load);
  allEl.addEventListener('change', load);
  $('e32a-refresh').addEventListener('click', load);

  load();
  // Keep the screen fresh when several people are keeping score.
  setInterval(function () {
    var active = document.activeElement;
    var editing = active && active.closest && active.closest('form, input, select');
    if (!document.hidden && !editing) load();
  }, 15000);
})();
