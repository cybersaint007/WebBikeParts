@extends('layouts.master')
@section('title', 'Parts')

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') Crawler @endslot
        @slot('title') Parts @endslot
    @endcomponent

    <div class="alert alert-info d-flex align-items-center">
        <div class="flex-grow-1">
            @if ($scope['all_bikes'])
                <strong>Showing parts for: all crawled bikes</strong>
                @if ($scope['my_bike_count'] > 0)
                    — <a href="{{ route('parts.index', request()->except('all_bikes')) }}">Limit to my bikes</a>
                @endif
            @elseif ($scope['my_bike_count'] === 0)
                <strong>You haven't added any bikes yet.</strong>
                <a href="{{ route('my-bikes.index') }}">Add a bike</a> to start crawling, or
                <a href="{{ route('parts.index', array_merge(request()->all(), ['all_bikes' => 1])) }}">browse all bikes</a>.
            @else
                <strong>Showing parts for: My Bikes ({{ $scope['my_bike_count'] }})</strong>
                <span class="text-muted">— {{ implode(', ', $scope['my_bike_labels']) }}</span>
                — <a href="{{ route('parts.index', array_merge(request()->all(), ['all_bikes' => 1])) }}">Show all bikes</a>
            @endif
        </div>
    </div>

    <div class="row">
        {{-- Sidebar filters --}}
        <div class="col-xl-3 col-lg-4">
            <div class="card">
                <div class="card-header">
                    <div class="d-flex align-items-center">
                        <h5 class="fs-16 flex-grow-1 mb-0">Filters</h5>
                        <a href="{{ route('parts.index') }}" class="text-decoration-underline">Clear all</a>
                    </div>
                </div>

                <div class="card-body">
                    <form method="GET" action="{{ route('parts.index') }}">
                        <div class="mb-3">
                            <label class="form-label fw-medium">Search</label>
                            <input type="search" name="q" value="{{ request('q') }}" class="form-control"
                                   placeholder="Title, part #, fitment…">
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Category</label>
                            <select name="category" class="form-select">
                                <option value="">All categories</option>
                                @foreach ($facets['categories'] as $cat)
                                    <option value="{{ $cat }}" @selected(request('category') === $cat)>{{ $cat }}</option>
                                @endforeach
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Source</label>
                            <select name="source" class="form-select">
                                <option value="">All sources</option>
                                @foreach ($facets['sources'] as $src)
                                    <option value="{{ $src }}" @selected(request('source') === $src)>{{ $src }}</option>
                                @endforeach
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Condition</label>
                            <select name="condition" class="form-select">
                                <option value="">Any condition</option>
                                @foreach ($facets['conditions'] as $cond)
                                    <option value="{{ $cond }}" @selected(request('condition') === $cond)>{{ $cond }}</option>
                                @endforeach
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Price range</label>
                            <div class="d-flex gap-2">
                                <input type="number" step="0.01" name="price_min" value="{{ request('price_min') }}"
                                       class="form-control" placeholder="Min">
                                <input type="number" step="0.01" name="price_max" value="{{ request('price_max') }}"
                                       class="form-control" placeholder="Max">
                            </div>
                        </div>

                        <button type="submit" class="btn btn-primary w-100">Apply filters</button>
                    </form>
                </div>
            </div>
        </div>

        {{-- Listings grid --}}
        <div class="col-xl-9 col-lg-8">
            <div class="card">
                <div class="card-header">
                    <div class="d-flex flex-wrap align-items-center gap-2">
                        <input id="parts-q" type="search" class="form-control flex-grow-1"
                               style="max-width:380px"
                               placeholder="Instant search: title, part #, fitment…"
                               value="{{ request('q') }}">
                        <h5 class="card-title mb-0 ms-auto" id="parts-result-count">
                            Showing {{ $listings->firstItem() ?? 0 }}–{{ $listings->lastItem() ?? 0 }}
                            of {{ $listings->total() }} parts
                        </h5>
                    </div>
                </div>

                <div class="card-body" id="parts-grid-container">
                    @if ($listings->isEmpty())
                        <div class="text-center py-5" id="parts-empty-state">
                            <h5 class="text-muted">No cached matches.</h5>
                            <p class="text-muted">
                                Try clearing filters, or run a live search across eBay / Webike now.
                            </p>
                            <button type="button" class="btn btn-primary" id="live-search-btn" disabled>
                                <i class="ri-search-eye-line me-1"></i> Search live sources
                            </button>
                            <p class="text-muted fs-13 mt-2">Type a query in the search box above first.</p>
                        </div>
                    @else
                        <div class="row" id="parts-grid">
                            @foreach ($listings as $l)
                                <div class="col-xl-4 col-md-6">
                                    <div class="card h-100 shadow-none border">
                                        <div class="bg-light text-center" style="height:180px; overflow:hidden;">
                                            @if ($l->image_url)
                                                <img src="{{ $l->image_url }}" alt=""
                                                     style="max-height:180px; object-fit:contain;"
                                                     loading="lazy"
                                                     onerror="this.style.display='none'">
                                            @else
                                                <div class="d-flex align-items-center justify-content-center h-100 text-muted">
                                                    <i class="ri-image-line" style="font-size:3rem;"></i>
                                                </div>
                                            @endif
                                        </div>
                                        <div class="card-body">
                                            <a href="{{ route('parts.show', $l) }}" class="text-body">
                                                <h6 class="mb-2 text-truncate-two-lines" title="{{ $l->title }}">
                                                    {{ \Illuminate\Support\Str::limit($l->title, 80) }}
                                                </h6>
                                            </a>
                                            @if (!empty($bikeLabels[$l->bike_key] ?? null))
                                                <p class="text-muted fs-12 mb-2 mb-0" title="{{ $l->bike_key }}">
                                                    <i class="ri-motorbike-line me-1"></i>{{ $bikeLabels[$l->bike_key] }}
                                                </p>
                                            @endif
                                            <div class="d-flex gap-1 flex-wrap mb-2">
                                                <span class="badge bg-light text-muted">{{ $l->source_name }}</span>
                                                @if ($l->condition)
                                                    <span class="badge bg-info-subtle text-info">{{ $l->condition }}</span>
                                                @endif
                                                @if ($l->category && $l->category !== 'unknown')
                                                    <span class="badge bg-secondary-subtle text-secondary">{{ $l->category }}</span>
                                                @endif
                                                @php
                                                    $hay = mb_strtolower(($l->title ?? '') . ' ' . ($l->description ?? ''));
                                                    $watched = false;
                                                    foreach ($watchQueries as $q) {
                                                        if ($q !== '' && str_contains($hay, $q)) { $watched = true; break; }
                                                    }
                                                @endphp
                                                @if ($watched)
                                                    <span class="badge bg-warning-subtle text-warning" title="Matches an active watch">
                                                        ★ Watched
                                                    </span>
                                                @endif
                                            </div>
                                            <div class="d-flex align-items-center mb-3">
                                                <h5 class="mb-0 me-2">
                                                    @if ($l->price_amount !== null)
                                                        {{ number_format((float) $l->price_amount, 2) }}
                                                        <small class="text-muted fs-13">{{ $l->price_currency }}</small>
                                                    @else
                                                        <span class="text-muted fs-14">Price n/a</span>
                                                    @endif
                                                </h5>
                                            </div>
                                            <a href="{{ $l->url }}" target="_blank" rel="noopener noreferrer"
                                               class="btn btn-sm btn-outline-primary w-100">
                                                View on {{ $l->source_name }}
                                                <i class="ri-external-link-line ms-1"></i>
                                            </a>
                                            <p class="text-muted fs-12 mt-2 mb-0">
                                                Last seen {{ $l->last_seen_at?->diffForHumans() }}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            @endforeach
                        </div>

                        <div class="mt-3" id="parts-pagination">
                            {{ $listings->links() }}
                        </div>
                    @endif
                </div>
            </div>
        </div>
    </div>
@endsection

@section('script')
<script>
(function () {
    const qInput  = document.getElementById('parts-q');
    const grid    = document.getElementById('parts-grid');
    const grid_c  = document.getElementById('parts-grid-container');
    const counter = document.getElementById('parts-result-count');
    const liveBtn = document.getElementById('live-search-btn');
    const allBikes = new URLSearchParams(window.location.search).get('all_bikes') === '1';

    if (!qInput) return;

    function escapeHtml(s) {
        return (s || '').replace(/[&<>"']/g, c =>
            ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function renderCard(l) {
        const img = l.image_url
            ? `<img src="${escapeHtml(l.image_url)}" loading="lazy" style="max-height:180px; object-fit:contain;" onerror="this.style.display='none'">`
            : `<div class="d-flex align-items-center justify-content-center h-100 text-muted"><i class="ri-image-line" style="font-size:3rem;"></i></div>`;
        const condBadge = l.condition ? `<span class="badge bg-info-subtle text-info">${escapeHtml(l.condition)}</span>` : '';
        const catBadge = (l.category && l.category !== 'unknown') ? `<span class="badge bg-secondary-subtle text-secondary">${escapeHtml(l.category)}</span>` : '';
        const price = (l.price_amount !== null && l.price_amount !== undefined)
            ? `${Number(l.price_amount).toFixed(2)} <small class="text-muted fs-13">${escapeHtml(l.price_currency || '')}</small>`
            : `<span class="text-muted fs-14">Price n/a</span>`;
        return `
        <div class="col-xl-4 col-md-6">
            <div class="card h-100 shadow-none border">
                <div class="bg-light text-center" style="height:180px; overflow:hidden;">${img}</div>
                <div class="card-body">
                    <a href="${escapeHtml(l.show_url)}" class="text-body">
                        <h6 class="mb-2 text-truncate-two-lines">${escapeHtml(l.title.slice(0, 80))}</h6>
                    </a>
                    ${l.bike_label ? `<p class="text-muted fs-12 mb-2" title="${escapeHtml(l.bike_key || '')}"><i class="ri-motorbike-line me-1"></i>${escapeHtml(l.bike_label)}</p>` : ''}
                    <div class="d-flex gap-1 flex-wrap mb-2">
                        <span class="badge bg-light text-muted">${escapeHtml(l.source_name)}</span>
                        ${condBadge}${catBadge}
                    </div>
                    <h5 class="mb-3">${price}</h5>
                    <a href="${escapeHtml(l.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary w-100">
                        View on ${escapeHtml(l.source_name)} <i class="ri-external-link-line ms-1"></i>
                    </a>
                    <p class="text-muted fs-12 mt-2 mb-0">Last seen ${escapeHtml(l.last_seen_human || '')}</p>
                </div>
            </div>
        </div>`;
    }

    function renderEmpty(q) {
        return `
        <div class="text-center py-5" id="parts-empty-state">
            <h5 class="text-muted">No cached matches for "${escapeHtml(q)}".</h5>
            <p class="text-muted">Run a live search across eBay / Webike now and we'll save it to your watch list.</p>
            <button type="button" class="btn btn-primary" id="live-search-btn">
                <i class="ri-search-eye-line me-1"></i> Search live sources
            </button>
        </div>`;
    }

    let currentReq = null;

    async function runSearch(q) {
        const params = new URLSearchParams(window.location.search);
        if (q) params.set('q', q); else params.delete('q');
        params.delete('page'); // reset paging
        // Update the URL so bookmarks work
        const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newUrl);

        try {
            if (currentReq) currentReq.abort();
            currentReq = new AbortController();
            const r = await fetch('/parts/search.json?' + params.toString(), {
                headers: { 'Accept': 'application/json' },
                signal: currentReq.signal,
            });
            if (!r.ok) return;
            const data = await r.json();

            counter.textContent = data.total === 0
                ? '0 parts'
                : `Showing ${data.pagination.first_item}–${data.pagination.last_item} of ${data.total} parts`;

            if (data.total === 0) {
                grid_c.innerHTML = renderEmpty(q);
                attachLiveBtn();
            } else {
                grid_c.innerHTML = '<div class="row">' + data.data.map(renderCard).join('') + '</div>';
            }
        } catch (e) {
            if (e.name !== 'AbortError') console.warn(e);
        }
    }

    let debounceTimer;
    qInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => runSearch(qInput.value.trim()), 250);
    });

    function attachLiveBtn() {
        const btn = document.getElementById('live-search-btn');
        if (!btn) return;
        btn.disabled = !qInput.value.trim();
        btn.addEventListener('click', launchLiveSearch);
    }

    qInput.addEventListener('input', () => {
        const btn = document.getElementById('live-search-btn');
        if (btn) btn.disabled = !qInput.value.trim();
    });

    async function launchLiveSearch() {
        const q = qInput.value.trim();
        if (!q) return;
        const btn = document.getElementById('live-search-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Searching live sources…';

        const formData = new FormData();
        formData.append('_token', document.querySelector('meta[name="csrf-token"]')?.content || '{{ csrf_token() }}');
        formData.append('q', q);
        const r = await fetch('{{ route("parts.live-search") }}', {
            method: 'POST',
            headers: { 'Accept': 'application/json', 'X-CSRF-TOKEN': '{{ csrf_token() }}' },
            body: formData,
        });
        if (!r.ok) {
            btn.innerHTML = 'Live search failed';
            return;
        }
        const data = await r.json();

        // Poll the run until success/failed
        const tick = async () => {
            try {
                const sr = await fetch(data.status_url, { headers: { 'Accept': 'application/json' } });
                const s = await sr.json();
                if (s.status === 'success' || s.status === 'failed') {
                    runSearch(qInput.value.trim());
                    btn.innerHTML = '<i class="ri-search-eye-line me-1"></i> Search live sources';
                    btn.disabled = !qInput.value.trim();
                } else {
                    setTimeout(tick, 3000);
                }
            } catch (e) { setTimeout(tick, 5000); }
        };
        setTimeout(tick, 3000);
    }

    attachLiveBtn();
})();
</script>
@endsection
