@extends('layouts.master')
@section('title', __('Dashboard'))

@section('content')
    {{-- Page title --}}
    <div class="d-flex align-items-center mb-3">
        <h4 class="mb-0 flex-grow-1">{{ __('Dashboard') }}</h4>
        <span class="text-muted fs-13">{{ __('Welcome back, :name', ['name' => auth()->user()->name]) }}</span>
    </div>

    {{-- Hero search --}}
    <div class="row justify-content-center mb-4">
        <div class="col-xl-8 col-lg-10">
            <div class="card shadow-sm">
                <div class="card-body p-4">
                    <h5 class="text-center mb-1">{{ __('Find motorcycle parts') }}</h5>
                    <p class="text-center text-muted fs-13 mb-3">
                        {{ __('Searches eBay, Webike, Buyee, Yahoo Auctions, and more') }}
                    </p>
                    <div class="input-group input-group-lg">
                        <input type="text" id="dashboard-q" class="form-control"
                               placeholder="{{ __('e.g. exhaust pipe, brake pads, air filter…') }}"
                               autofocus autocomplete="off">
                        <button class="btn btn-primary" id="dashboard-search-btn" type="button" disabled>
                            <i class="ri-search-eye-line me-1"></i>{{ __('Search live sources') }}
                        </button>
                    </div>
                    <div id="dashboard-search-status" class="text-muted small mt-2 text-center d-none"></div>
                </div>
            </div>
        </div>
    </div>

    {{-- Stats cards --}}
    <div class="row">
        <div class="col-xl-3 col-md-6">
            <div class="card card-animate">
                <div class="card-body">
                    <p class="text-uppercase fw-medium text-muted text-truncate mb-0">{{ __('Bikes tracked') }}</p>
                    <div class="d-flex align-items-end justify-content-between mt-4">
                        <div>
                            <h4 class="fs-22 fw-semibold ff-secondary mb-4">{{ $bikesCount }}</h4>
                            <a href="{{ route('my-bikes.index') }}" class="text-decoration-underline text-muted">{{ __('Manage bikes') }}</a>
                        </div>
                        <div class="avatar-sm flex-shrink-0">
                            <span class="avatar-title bg-success-subtle rounded fs-3">
                                <i class="ri-motorbike-line text-success"></i>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="col-xl-3 col-md-6">
            <div class="card card-animate">
                <div class="card-body">
                    <p class="text-uppercase fw-medium text-muted text-truncate mb-0">{{ __('Parts found') }}</p>
                    <div class="d-flex align-items-end justify-content-between mt-4">
                        <div>
                            <h4 class="fs-22 fw-semibold ff-secondary mb-4">{{ number_format($partsCount) }}</h4>
                            <a href="{{ route('parts.index') }}" class="text-decoration-underline text-muted">{{ __('Browse parts') }}</a>
                        </div>
                        <div class="avatar-sm flex-shrink-0">
                            <span class="avatar-title bg-primary-subtle rounded fs-3">
                                <i class="ri-search-line text-primary"></i>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="col-xl-3 col-md-6">
            <div class="card card-animate">
                <div class="card-body">
                    <p class="text-uppercase fw-medium text-muted text-truncate mb-0">{{ __('Active watches') }}</p>
                    <div class="d-flex align-items-end justify-content-between mt-4">
                        <div>
                            <h4 class="fs-22 fw-semibold ff-secondary mb-4">{{ $watchesCount }}</h4>
                            <a href="{{ route('watch-list.index') }}" class="text-decoration-underline text-muted">{{ __('View watch list') }}</a>
                        </div>
                        <div class="avatar-sm flex-shrink-0">
                            <span class="avatar-title bg-warning-subtle rounded fs-3">
                                <i class="ri-bookmark-star-line text-warning"></i>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="col-xl-3 col-md-6">
            <div class="card card-animate">
                <div class="card-body">
                    <p class="text-uppercase fw-medium text-muted text-truncate mb-0">{{ __('New this week') }}</p>
                    <div class="d-flex align-items-end justify-content-between mt-4">
                        <div>
                            <h4 class="fs-22 fw-semibold ff-secondary mb-4">{{ number_format($newThisWeek) }}</h4>
                            <span class="text-muted fs-13">{{ __('listings in last 7 days') }}</span>
                        </div>
                        <div class="avatar-sm flex-shrink-0">
                            <span class="avatar-title bg-info-subtle rounded fs-3">
                                <i class="ri-time-line text-info"></i>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    {{-- My bikes grid --}}
    <div class="card">
        <div class="card-header d-flex align-items-center">
            <h5 class="mb-0 flex-grow-1">{{ __('My Bikes') }}</h5>
            @if ($totalBikes > 6)
                <a href="{{ route('my-bikes.index') }}" class="fs-13">{{ __('View all') }} ({{ $totalBikes }}) →</a>
            @else
                <a href="{{ route('my-bikes.index') }}" class="fs-13">{{ __('Manage') }} →</a>
            @endif
        </div>
        <div class="card-body">
            @if ($userBikes->isEmpty())
                <div class="text-center py-4">
                    <i class="ri-motorbike-line text-muted" style="font-size:3rem;"></i>
                    <p class="text-muted mt-2 mb-3">{{ __('No bikes yet. Add your first bike to start finding parts.') }}</p>
                    <a href="{{ route('my-bikes.index') }}" class="btn btn-primary btn-sm">{{ __('Add a bike') }}</a>
                </div>
            @else
                <div class="row">
                    @foreach ($userBikes as $ub)
                        @php
                            $cat = $catalogs->get($ub->bike_catalog_id);
                            $run = $cat ? $latestRuns->get($cat->catalog_key) : null;
                        @endphp
                        <div class="col-xl-2 col-lg-3 col-md-4 col-sm-6 mb-3">
                            <div class="card border h-100 mb-0">
                                <div class="position-relative"
                                     style="height:120px;overflow:hidden;border-radius:calc(var(--bs-card-border-radius,0.375rem) - var(--bs-card-border-width,1px)) calc(var(--bs-card-border-radius,0.375rem) - var(--bs-card-border-width,1px)) 0 0">
                                    @if ($cat?->image_url)
                                        <img src="{{ $cat->image_url }}" alt="{{ $cat->displayLabel() }}"
                                             style="width:100%;height:100%;object-fit:contain;background:#f8f9fa;">
                                    @else
                                        <div class="bg-light d-flex align-items-center justify-content-center h-100">
                                            <i class="ri-motorbike-line text-muted" style="font-size:2.5rem;"></i>
                                        </div>
                                    @endif
                                </div>
                                <div class="card-body p-2">
                                    <p class="mb-1 fw-medium fs-13 text-truncate" title="{{ $cat?->displayLabel() ?? '—' }}">
                                        {{ $cat?->displayLabel() ?? '—' }}
                                    </p>
                                    @if ($ub->nickname)
                                        <p class="text-muted fs-12 mb-1 text-truncate">{{ $ub->nickname }}</p>
                                    @endif
                                    @if ($run)
                                        @php
                                            $runClass = match($run->status) {
                                                'success' => 'bg-success-subtle text-success',
                                                'failed'  => 'bg-danger-subtle text-danger',
                                                default   => 'bg-secondary-subtle text-muted',
                                            };
                                        @endphp
                                        <span class="badge fs-11 {{ $runClass }}">
                                            {{ $run->finished_at?->diffForHumans() ?? $run->status }}
                                        </span>
                                    @else
                                        <span class="badge bg-secondary-subtle text-muted fs-11">{{ __('not crawled') }}</span>
                                    @endif
                                    @if ($cat)
                                        <div class="mt-2">
                                            <a href="{{ route('parts.index', ['bike' => $cat->catalog_key]) }}"
                                               class="btn btn-sm btn-outline-primary w-100 fs-12 py-1">
                                                {{ __('Browse parts') }}
                                            </a>
                                        </div>
                                    @endif
                                </div>
                            </div>
                        </div>
                    @endforeach
                </div>
            @endif
        </div>
    </div>

    <div class="row">
        {{-- Watch summary --}}
        <div class="col-xl-6">
            <div class="card h-100">
                <div class="card-header d-flex align-items-center">
                    <h5 class="mb-0 flex-grow-1">{{ __('Top Watches') }}</h5>
                    <a href="{{ route('watch-list.index') }}" class="fs-13">{{ __('View all') }} →</a>
                </div>
                <div class="card-body p-0">
                    @if ($topWatches->isEmpty())
                        <div class="text-center py-4">
                            <p class="text-muted mb-0">{{ __('No saved searches yet. Use the search bar above to get started.') }}</p>
                        </div>
                    @else
                        <table class="table mb-0 align-middle">
                            <thead>
                                <tr>
                                    <th>{{ __('Query') }}</th>
                                    <th>{{ __('Bike') }}</th>
                                    <th class="text-end">{{ __('Matches') }}</th>
                                    <th>{{ __('Last crawled') }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                @foreach ($topWatches as $w)
                                    @php($wCat = $w->bike_catalog_id ? $watchBikes->get($w->bike_catalog_id) : null)
                                    <tr>
                                        <td>
                                            <a href="{{ route('parts.index', ['q' => $w->query]) }}" class="fw-medium">
                                                {{ $w->query }}
                                            </a>
                                            @if ($w->is_high_priority)
                                                <span class="badge bg-warning-subtle text-warning ms-1">★</span>
                                            @endif
                                        </td>
                                        <td class="text-muted fs-12">
                                            {{ $wCat?->displayLabel() ?? __('All bikes') }}
                                        </td>
                                        <td class="text-end fw-medium">{{ $w->match_count }}</td>
                                        <td class="text-muted fs-12">{{ $w->last_crawled_at?->diffForHumans() ?? '—' }}</td>
                                    </tr>
                                @endforeach
                            </tbody>
                        </table>
                    @endif
                </div>
            </div>
        </div>

        {{-- Recent sync activity --}}
        <div class="col-xl-6">
            <div class="card h-100">
                <div class="card-header">
                    <h5 class="mb-0">{{ __('Recent Activity') }}</h5>
                </div>
                <div class="card-body p-0">
                    @if ($recentSyncs->isEmpty())
                        <div class="text-center py-4">
                            <p class="text-muted mb-0">{{ __('No activity yet.') }}</p>
                        </div>
                    @else
                        <table class="table mb-0 align-middle">
                            <thead>
                                <tr>
                                    <th>{{ __('Kind') }}</th>
                                    <th>{{ __('Status') }}</th>
                                    <th>{{ __('Finished') }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                @foreach ($recentSyncs as $s)
                                    @php
                                        $sBadge = match($s->status) {
                                            'success' => 'bg-success-subtle text-success',
                                            'failed'  => 'bg-danger-subtle text-danger',
                                            'running' => 'bg-primary-subtle text-primary',
                                            default   => 'bg-secondary-subtle text-muted',
                                        };
                                    @endphp
                                    <tr>
                                        <td class="fw-medium fs-13">{{ str_replace('_', ' ', $s->kind) }}</td>
                                        <td><span class="badge {{ $sBadge }}">{{ $s->status }}</span></td>
                                        <td class="text-muted fs-12">
                                            {{ $s->finished_at?->diffForHumans() ?? ($s->started_at?->diffForHumans() ?? __('pending')) }}
                                        </td>
                                    </tr>
                                @endforeach
                            </tbody>
                        </table>
                    @endif
                </div>
            </div>
        </div>
    </div>

    {{-- Admin: crawler queue health --}}
    @if (auth()->user()->isAdmin() && $jobStats !== null)
        <div class="card mt-3">
            <div class="card-body py-3 d-flex align-items-center flex-wrap gap-2">
                <span class="fw-medium me-1">{{ __('Crawler queue:') }}</span>
                @foreach (['pending', 'running', 'success', 'failed'] as $st)
                    @php
                        $cnt = $jobStats->get($st, 0);
                        $cls = match($st) {
                            'pending' => 'bg-secondary-subtle text-muted',
                            'running' => 'bg-primary-subtle text-primary',
                            'success' => 'bg-success-subtle text-success',
                            'failed'  => 'bg-danger-subtle text-danger',
                        };
                    @endphp
                    <span class="badge {{ $cls }}">{{ $st }}: {{ $cnt }}</span>
                @endforeach
            </div>
        </div>
    @endif

    {{-- Search JS --}}
    @php
        $dashI18n = [
            'searching'   => __('Searching live sources…'),
            'dispatching' => __('Dispatching search job…'),
            'inProgress'  => __('Searching… this may take up to a minute.'),
            'failed'      => __('Failed to start search. Please try again.'),
            'searchLive'  => __('Search live sources'),
            'netError'    => __('Network error. Please try again.'),
        ];
    @endphp
    <script>
    (function () {
        const I18N     = @json($dashI18n);
        const qInput   = document.getElementById('dashboard-q');
        const btn      = document.getElementById('dashboard-search-btn');
        const statusEl = document.getElementById('dashboard-search-status');
        const liveSearchUrl = '{{ route("parts.live-search") }}';
        const csrfToken     = document.querySelector('meta[name="csrf-token"]')?.content || '{{ csrf_token() }}';

        qInput.addEventListener('input', () => { btn.disabled = !qInput.value.trim(); });
        qInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && qInput.value.trim()) launchLiveSearch(); });
        btn.addEventListener('click', launchLiveSearch);

        async function launchLiveSearch() {
            const q = qInput.value.trim();
            if (!q) return;

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + I18N.searching;
            statusEl.textContent = I18N.dispatching;
            statusEl.classList.remove('d-none');

            const fd = new FormData();
            fd.append('q', q);

            try {
                const r = await fetch(liveSearchUrl, {
                    method: 'POST',
                    headers: { Accept: 'application/json', 'X-CSRF-TOKEN': csrfToken },
                    body: fd,
                });
                if (!r.ok) {
                    statusEl.textContent = I18N.failed;
                    btn.innerHTML = '<i class="ri-search-eye-line me-1"></i>' + I18N.searchLive;
                    btn.disabled = false;
                    return;
                }
                const data = await r.json();
                statusEl.textContent = I18N.inProgress;

                const tick = async () => {
                    try {
                        const sr = await fetch(data.status_url, { headers: { Accept: 'application/json' } });
                        const s  = await sr.json();
                        if (s.status === 'success' || s.status === 'failed') {
                            window.location.href = '/parts?q=' + encodeURIComponent(q);
                        } else {
                            setTimeout(tick, 3000);
                        }
                    } catch (_) { setTimeout(tick, 5000); }
                };
                setTimeout(tick, 3000);
            } catch (_) {
                statusEl.textContent = I18N.netError;
                btn.innerHTML = '<i class="ri-search-eye-line me-1"></i>' + I18N.searchLive;
                btn.disabled = false;
            }
        }
    })();
    </script>
@endsection
