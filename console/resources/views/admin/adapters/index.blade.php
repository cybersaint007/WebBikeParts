@extends('layouts.master')
@section('title', 'Adapter Status')

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') Admin @endslot
        @slot('title') Adapter Status @endslot
    @endcomponent

    <div class="card" id="adapter-status-card"
         data-poll-url="{{ $pollUrl }}"
         data-poll-period="{{ $pollPeriod }}">
        <div class="card-header d-flex align-items-center gap-2 flex-wrap">
            <h5 class="mb-0 flex-grow-1">Adapters</h5>

            <span class="text-muted fs-13">
                Stuck threshold: <strong id="stale-mins">—</strong> min &middot;
                Last update: <strong id="last-update">never</strong>
            </span>

            <div class="form-check form-switch ms-2">
                <input class="form-check-input" type="checkbox" id="auto-refresh" checked>
                <label class="form-check-label" for="auto-refresh">Auto-refresh</label>
            </div>

            <button type="button" id="refresh-now" class="btn btn-sm btn-outline-primary">
                <i class="ri-refresh-line"></i> Refresh
            </button>
        </div>

        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table align-middle mb-0" id="adapter-status-table">
                    <thead class="table-light">
                        <tr>
                            <th>Adapter</th>
                            <th>Health</th>
                            <th>Enabled</th>
                            <th class="text-end">Pending</th>
                            <th class="text-end">Running</th>
                            <th class="text-end">Completed</th>
                            <th class="text-end">Failed</th>
                            <th class="text-end">Stuck</th>
                            <th class="text-end">Ingested</th>
                            <th>Last completed</th>
                            <th>Last error</th>
                        </tr>
                    </thead>
                    <tbody id="adapter-status-rows">
                        <tr>
                            <td colspan="11" class="text-center text-muted p-4">
                                <div class="spinner-border spinner-border-sm me-2"></div>
                                Loading adapter status…
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card-footer">
            <small class="text-muted">
                Counts come from <code>watcher.crawl_jobs</code>; "Stuck" = jobs in <code>running</code>
                whose <code>locked_at</code> is older than the stuck threshold.
                "Disabled" health means <code>watcher.sources.enabled = false</code>.
            </small>
        </div>
    </div>

<script>
(function () {
    const card = document.getElementById('adapter-status-card');
    const url = card.dataset.pollUrl;
    const periodMs = parseInt(card.dataset.pollPeriod, 10) || 5000;
    const tbody = document.getElementById('adapter-status-rows');
    const updatedEl = document.getElementById('last-update');
    const staleEl = document.getElementById('stale-mins');
    const autoEl = document.getElementById('auto-refresh');
    const refreshBtn = document.getElementById('refresh-now');

    const HEALTH_CLASS = {
        disabled: 'bg-secondary-subtle text-secondary',
        idle:     'bg-success-subtle text-success',
        queued:   'bg-info-subtle text-info',
        running:  'bg-primary-subtle text-primary',
        failing:  'bg-danger-subtle text-danger',
        stuck:    'bg-warning-subtle text-warning',
        unknown:  'bg-light text-muted',
    };

    function fmtTime(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            const now = new Date();
            const diff = (now - d) / 1000;
            if (diff < 60)        return Math.floor(diff) + 's ago';
            if (diff < 3600)      return Math.floor(diff / 60) + 'm ago';
            if (diff < 86400)     return Math.floor(diff / 3600) + 'h ago';
            return d.toISOString().slice(0, 10);
        } catch (_) { return iso; }
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function render(payload) {
        staleEl.textContent = payload.stale_lock_minutes ?? '—';
        updatedEl.textContent = new Date(payload.fetched_at).toLocaleTimeString();

        if (!payload.adapters || payload.adapters.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center text-muted p-4">No adapters reported.</td></tr>';
            return;
        }

        const rows = payload.adapters.map(a => {
            const cls = HEALTH_CLASS[a.health] || HEALTH_CLASS.unknown;
            const enabledBadge = a.enabled === null
                ? '<span class="badge bg-light text-muted">no source row</span>'
                : (a.enabled
                    ? '<span class="badge bg-success-subtle text-success">on</span>'
                    : '<span class="badge bg-secondary-subtle text-secondary">off</span>');

            const errCell = a.last_error
                ? `<span class="text-danger" title="${escapeHtml(a.last_error)}">${escapeHtml(a.last_error.split('\n')[0].slice(0, 80))}</span>
                   <div class="text-muted fs-12">${fmtTime(a.last_error_at)}</div>`
                : '<span class="text-muted">—</span>';

            return `
                <tr>
                    <td>
                        <strong>${escapeHtml(a.adapter)}</strong>
                        ${a.type ? `<div class="text-muted fs-12">${escapeHtml(a.type)}</div>` : ''}
                    </td>
                    <td><span class="badge ${cls} text-uppercase">${escapeHtml(a.health)}</span></td>
                    <td>${enabledBadge}</td>
                    <td class="text-end">${a.pending}</td>
                    <td class="text-end">${a.running}</td>
                    <td class="text-end">${a.completed}</td>
                    <td class="text-end ${a.failed > 0 ? 'text-danger fw-semibold' : ''}">${a.failed}</td>
                    <td class="text-end ${a.stuck > 0 ? 'text-warning fw-semibold' : ''}">${a.stuck}</td>
                    <td class="text-end">${a.total_ingested}</td>
                    <td>${fmtTime(a.last_completed_at)}</td>
                    <td>${errCell}</td>
                </tr>
            `;
        }).join('');

        tbody.innerHTML = rows;
    }

    let timer = null;
    let inFlight = false;

    async function tick() {
        if (inFlight) return;
        inFlight = true;
        try {
            const res = await fetch(url, {
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            render(await res.json());
        } catch (e) {
            updatedEl.textContent = 'failed (' + e.message + ')';
        } finally {
            inFlight = false;
        }
    }

    function startTimer() {
        if (timer) return;
        timer = setInterval(tick, periodMs);
    }
    function stopTimer() {
        if (!timer) return;
        clearInterval(timer);
        timer = null;
    }

    autoEl.addEventListener('change', () => autoEl.checked ? startTimer() : stopTimer());
    refreshBtn.addEventListener('click', tick);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopTimer();
        else if (autoEl.checked) startTimer();
    });

    tick();
    startTimer();
})();
</script>
@endsection

