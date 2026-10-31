document.addEventListener('DOMContentLoaded', () => {
    const body = document.getElementById('scoreboardBody');
    const refresh = document.getElementById('refreshScoreboard');
    const status = document.getElementById('scoreboardStatus');
    const updated = document.getElementById('scoreboardUpdated');
    const view = document.getElementById('standingsView');
    let frozen = false;
    const isAdmin = document.getElementById('scoreboardTable').dataset.isAdmin === 'true';
    let socket, loading = false, received = false, revision = 0;
    const setStatus = (state, message) => { if (frozen && !isAdmin) {state = 'frozen'; message = 'Public standings frozen';} status.dataset.state = state; document.getElementById('scoreboardStatusText').textContent = message; };
    function render(rows) {
        if (!Array.isArray(rows)) throw new Error('Invalid leaderboard response');
        received = true;
        body.replaceChildren();
        if (!rows.length) {
            const row = body.insertRow(); const cell = row.insertCell(); cell.colSpan = 4;
            cell.className = 'text-center py-5 text-muted';
            cell.textContent = view.value === 'nearby' ? 'You have no ranked entry in this competition mode.' : 'No scores yet. Rankings will appear as participants start competing.';
        }
        rows.forEach((entry, index) => {
            const row = body.insertRow();
            if (String(entry.id) === document.getElementById('scoreboardTable').dataset.entrantId) row.className = 'own-standing';
            const rank = row.insertCell(); rank.className = 'rank-cell'; rank.textContent = entry.rank ?? index + 1;
            if (entry.rank >= 1 && entry.rank <= 3) rank.classList.add(`rank-${entry.rank}`);
            const name = row.insertCell();
            const label = document.createElement('div'); label.className = 'team-name'; label.textContent = entry.name || 'Unnamed participant'; name.append(label);
            if (row.classList.contains('own-standing')) { const you = document.createElement('small'); you.textContent = 'Your entry'; name.append(you); }
            if (entry.first_bloods) { const first = document.createElement('div'); first.className = 'first-blood'; first.textContent = `${entry.first_bloods} first blood${entry.first_bloods === 1 ? '' : 's'}`; name.append(first); }
            if (entry.affiliation) { const affiliation = document.createElement('div'); affiliation.className = 'team-affiliation'; affiliation.textContent = entry.affiliation; name.append(affiliation); }
            const score = row.insertCell(); score.className = `score-cell${entry.score < 0 ? ' text-danger' : ''}`; score.textContent = entry.score ?? 0;
            const solves = row.insertCell(); solves.className = 'solves-cell'; solves.textContent = entry.solves ?? 0;
        });
        updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
    async function load() {
        if (loading) return;
        loading = true; refresh.disabled = true;
        const requestRevision = revision;
        const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetchWithCSRF('/scoreboard/api/data' + (view.value === 'nearby' ? '?nearby=1' : ''), { signal: controller.signal, cache: 'no-store' });
            if (response.redirected && new URL(response.url).pathname === '/login') {
                body.replaceChildren();
                window.location.assign(response.url);
                return;
            }
            if (!response.ok) throw new Error('Leaderboard unavailable');
            const rows = await response.json();
            // A newer socket update must not be replaced by an older HTTP response.
            if (requestRevision === revision) render(rows);
            setStatus(socket?.connected ? 'live' : 'polling', socket?.connected ? 'Live updates connected' : 'Refreshing every 30 seconds');
        } catch (_) {
            updated.textContent = 'Update failed - use Refresh to retry';
            setStatus('error', 'Update failed · use Refresh to retry');
            if (!received) { body.innerHTML = '<tr><td colspan="4" class="text-center py-5">Unable to load rankings. Use Refresh to try again.</td></tr>'; }
        } finally { clearTimeout(timeout); loading = false; refresh.disabled = false; if (requestRevision !== revision) load(); }
    }
    refresh.addEventListener('click', load);
    view.addEventListener('change', () => { revision++; load(); });
    window.addEventListener('competition-status', event => {
        const wasFrozen = frozen; frozen = Boolean(event.detail.frozen_at);
        const notice = document.getElementById('freezeNotice'); notice.hidden = !frozen;
        notice.textContent = frozen ? `Standings frozen at ${new Date(event.detail.frozen_at).toLocaleString()}. ${isAdmin ? 'You are viewing live admin standings.' : 'New solves will appear when admins unfreeze the board.'}` : '';
        if (wasFrozen !== frozen) {revision++; load();}
        if (frozen) setStatus('frozen', 'Public standings frozen');
    });
    load();
    if (typeof io === 'function') {
        socket = window.liveSocket || io('/live', { transports: ['polling', 'websocket'] });
        socket.on('connect', () => { setStatus('live', 'Live updates connected'); socket.emit('join_scoreboard'); if (received && !loading) load(); });
        socket.on('scoreboard_update', rows => { if (Array.isArray(rows) && (!frozen || isAdmin)) { revision++; if (view.value === 'nearby') load(); else render(rows); } });
        socket.on('scoreboard_freeze', data => { frozen = data.frozen; revision++; window.location.reload(); });
        socket.on('scoreboard_visibility', data => {
            if (!data.visible && document.getElementById('scoreboardTable').dataset.isAdmin !== 'true') {
                body.replaceChildren();
                window.location.reload();
            }
        });
        socket.on('disconnect', () => setStatus('polling', 'Reconnecting · refreshing every 30 seconds'));
        socket.on('connect_error', () => setStatus('polling', 'Live connection unavailable · refreshing every 30 seconds'));
    }
    async function checkFreeze() {
        try {
            const response = await fetchWithCSRF('/api/competition-status', {cache: 'no-store'});
            if (response.ok && !response.redirected) window.dispatchEvent(new CustomEvent('competition-status', {detail: await response.json()}));
        } catch (_) { /* Keep the current board during a temporary outage. */ }
    }
    checkFreeze();
    const freezeInterval = setInterval(checkFreeze, 15000);
    const interval = setInterval(() => { if (!document.hidden) load(); }, 30000);
    window.addEventListener('pagehide', () => { clearInterval(interval); clearInterval(freezeInterval); socket?.disconnect(); });
});
