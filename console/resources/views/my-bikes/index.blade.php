@extends('layouts.master')
@section('title', __('My Bikes'))

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') {{ __('Crawler') }} @endslot
        @slot('title') {{ __('My Bikes') }} @endslot
    @endcomponent

    @if (session('status'))
        <div class="alert alert-success">{{ session('status') }}</div>
    @endif

    {{-- Catalog refresh widget --}}
    <div class="card">
        <div class="card-body d-flex flex-wrap align-items-center gap-3">
            <div class="flex-grow-1">
                <h6 class="mb-1">{{ __('Bike catalog') }}</h6>
                <p class="text-muted mb-0 fs-13">
                    @if ($latestCatalog?->finished_at)
                        {{ __('Last updated :time (:date).', [
                            'time' => $latestCatalog->finished_at->diffForHumans(),
                            'date' => $latestCatalog->finished_at->format('Y-m-d H:i'),
                        ]) }}
                    @else
                        {{ __('Catalog has never been synced from webike.tw.') }}
                    @endif
                </p>
            </div>
            @if ($catalogInflight)
                <button class="btn btn-secondary" disabled
                        data-sync-poll="{{ route('sync.show', $catalogInflight) }}">
                    <span class="spinner-border spinner-border-sm me-1"></span>
                    {{ $catalogInflight->status === 'running' ? __('Refreshing…') : __('Queued…') }}
                </button>
            @else
                <form method="POST" action="{{ route('sync.store') }}" class="m-0">
                    @csrf
                    <input type="hidden" name="kind" value="catalog">
                    <button type="submit" class="btn btn-primary">
                        <i class="ri-refresh-line me-1"></i> {{ __('Refresh from webike now') }}
                    </button>
                </form>
            @endif
        </div>
    </div>

    <div class="row">
        {{-- Saved bikes --}}
        <div class="col-lg-7">
            <div class="card">
                <div class="card-header"><h5 class="mb-0">{{ __("Bikes you're tracking") }}</h5></div>
                <div class="card-body">
                    @if ($userBikes->isEmpty())
                        <p class="text-muted mb-0">{{ __('Add a bike below to start crawling parts for it.') }}</p>
                    @else
                        <div class="row">
                            @foreach ($userBikes as $ub)
                                @php
                                    $cat = $catalogs->get($ub->bike_catalog_id);
                                    $run = $cat ? ($latestRuns->get($cat->catalog_key)) : null;
                                @endphp
                                <div class="col-md-6 mb-3">
                                    <div class="card border h-100 mb-0">
                                        <div class="position-relative" style="height:160px;overflow:hidden;border-radius:calc(var(--bs-card-border-radius, 0.375rem) - var(--bs-card-border-width, 1px)) calc(var(--bs-card-border-radius, 0.375rem) - var(--bs-card-border-width, 1px)) 0 0">
                                            @if ($cat?->image_url)
                                                <img src="{{ $cat->image_url }}"
                                                     alt="{{ $cat?->displayLabel() }}"
                                                     style="width:100%;height:100%;object-fit:contain;background:#f8f9fa;">
                                            @else
                                                <div class="bg-light d-flex align-items-center justify-content-center h-100">
                                                    <i class="ri-motorbike-line text-muted" style="font-size:3rem;"></i>
                                                </div>
                                            @endif
                                            @if ($cat)
                                                <div class="position-absolute top-0 end-0 m-1 d-flex gap-1" style="z-index:1;">
                                                    <label class="btn btn-sm btn-light border p-1 mb-0 upload-image-label"
                                                           for="img-upload-{{ $cat->catalog_key }}"
                                                           title="{{ __('Upload your own photo') }}"
                                                           style="line-height:1;opacity:.75;cursor:pointer;">
                                                        <i class="ri-upload-2-line"></i>
                                                    </label>
                                                    <input type="file" id="img-upload-{{ $cat->catalog_key }}"
                                                           accept="image/*" class="d-none upload-image-input"
                                                           data-upload-url="{{ route('my-bikes.upload-image', $cat->catalog_key) }}">
                                                    @if ($cat->webike_url)
                                                        <button type="button"
                                                                class="btn btn-sm btn-light border p-1 refresh-image-btn"
                                                                data-refresh-url="{{ route('my-bikes.refresh-image', $cat->catalog_key) }}"
                                                                title="{{ __('Search web for image') }}"
                                                                style="line-height:1;opacity:.75;">
                                                            <i class="ri-camera-line"></i>
                                                        </button>
                                                    @endif
                                                </div>
                                            @endif
                                        </div>
                                        <div class="card-body">
                                            <h6 class="mb-1">
                                                {{ $cat ? $cat->displayLabel() : __('Unknown bike (catalog id :id)', ['id' => $ub->bike_catalog_id]) }}
                                            </h6>
                                            @if ($ub->nickname)
                                                <p class="text-muted fs-13 mb-2">"{{ $ub->nickname }}"</p>
                                            @endif
                                            @if ($cat?->displacement_cc)
                                                <span class="badge bg-light text-muted">{{ $cat->displacement_cc }} cc</span>
                                            @endif
                                            <span class="badge bg-secondary-subtle text-secondary">{{ $cat?->catalog_key }}</span>

                                            <div class="mt-3 fs-13" data-bike-status="{{ $cat?->catalog_key }}">
                                                @if ($run && $run->isInFlight())
                                                    <span class="badge bg-warning-subtle text-warning"
                                                          data-sync-poll="{{ route('sync.show', $run) }}">
                                                        <span class="spinner-border spinner-border-sm me-1"></span>
                                                        {{ $run->status === 'running' ? __('Crawling…') : __('Crawl queued…') }}
                                                    </span>
                                                @elseif ($run?->status === 'success' && $run->finished_at)
                                                    <span class="text-success">
                                                        <i class="ri-check-line"></i>
                                                        {{ __('Updated :time', ['time' => $run->finished_at->diffForHumans()]) }}
                                                    </span>
                                                @elseif ($run?->status === 'failed')
                                                    <span class="text-danger" title="{{ $run->output_excerpt }}">
                                                        <i class="ri-error-warning-line"></i>
                                                        {{ __('Crawl failed — see sync_runs id :id', ['id' => $run->id]) }}
                                                    </span>
                                                @else
                                                    <span class="text-muted">{{ __('Awaiting first crawl.') }}</span>
                                                @endif
                                            </div>

                                            <form method="POST" action="{{ route('my-bikes.destroy', $ub) }}" class="mt-3">
                                                @csrf @method('DELETE')
                                                <button type="submit" class="btn btn-sm btn-outline-danger"
                                                        onclick="return confirm('{{ __('Remove this bike?') }}')">
                                                    {{ __('Remove') }}
                                                </button>
                                            </form>
                                        </div>
                                    </div>
                                </div>
                            @endforeach
                        </div>
                    @endif
                </div>
            </div>
        </div>

        {{-- Add bike form --}}
        <div class="col-lg-5">
            <div class="card">
                <div class="card-header"><h5 class="mb-0">{{ __('Add a bike') }}</h5></div>
                <div class="card-body">
                    <form method="POST" action="{{ route('my-bikes.store') }}" id="add-bike-form">
                        @csrf
                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Make') }}</label>
                            <select name="make" id="bike-make" class="form-select @error('make') is-invalid @enderror" required>
                                <option value="">{{ __('— Choose make —') }}</option>
                                @foreach ($makes as $m)
                                    <option value="{{ $m }}">{{ $m }}</option>
                                @endforeach
                            </select>
                            @error('make') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Model') }}</label>
                            <select name="model_slug" id="bike-model" class="form-select @error('model_slug') is-invalid @enderror" required disabled>
                                <option value="">{{ __('— Choose make first —') }}</option>
                            </select>
                            @error('model_slug') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Year') }}</label>
                            <select name="year" id="bike-year" class="form-select @error('year') is-invalid @enderror" required disabled>
                                <option value="">{{ __('— Choose model first —') }}</option>
                            </select>
                            @error('year') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Nickname (optional)') }}</label>
                            <input type="text" name="nickname" maxlength="120" class="form-control"
                                   placeholder="{{ __('e.g. My Fireblade') }}" value="{{ old('nickname') }}">
                        </div>

                        <button type="submit" class="btn btn-primary w-100">{{ __('Add bike') }}</button>
                    </form>

                    @if ($makes->isEmpty())
                        <div class="alert alert-warning mt-3 mb-0">
                            {!! __('The bike catalog is empty. Run :code to populate it from webike.tw.', ['code' => '<code>parts-watch sync-catalog</code>']) !!}
                        </div>
                    @endif
                </div>
            </div>
        </div>
    </div>
@endsection

@section('script')
@php
    $bikesI18n = [
        'loading'         => __('— Loading… —'),
        'chooseMakeFirst' => __('— Choose make first —'),
        'chooseModelFirst'=> __('— Choose model first —'),
        'chooseModel'     => __('— Choose model —'),
        'chooseYear'      => __('— Choose year —'),
        'anyYear'         => __('Any year'),
    ];
@endphp
<script>
const BIKES_I18N = @json($bikesI18n);
const CSRF_TOKEN = '{{ csrf_token() }}';

(function () {
    const makeSel  = document.getElementById('bike-make');
    const modelSel = document.getElementById('bike-model');
    const yearSel  = document.getElementById('bike-year');

    function reset(sel, placeholder) {
        sel.innerHTML = '<option value="">' + placeholder + '</option>';
        sel.disabled = true;
    }

    async function load(url) {
        const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!r.ok) throw new Error('lookup failed');
        return r.json();
    }

    makeSel.addEventListener('change', async () => {
        reset(modelSel, BIKES_I18N.loading);
        reset(yearSel,  BIKES_I18N.chooseModelFirst);
        if (!makeSel.value) { reset(modelSel, BIKES_I18N.chooseMakeFirst); return; }
        const models = await load('/api/catalog/models?make=' + encodeURIComponent(makeSel.value));
        modelSel.innerHTML = '<option value="">' + BIKES_I18N.chooseModel + '</option>' +
            models.map(m => `<option value="${m.model_slug}">${m.model}</option>`).join('');
        modelSel.disabled = false;
    });

    modelSel.addEventListener('change', async () => {
        reset(yearSel, BIKES_I18N.loading);
        if (!modelSel.value) { reset(yearSel, BIKES_I18N.chooseModelFirst); return; }
        const years = await load('/api/catalog/years?make=' + encodeURIComponent(makeSel.value)
                                + '&model_slug=' + encodeURIComponent(modelSel.value));
        const opts = years.map(y => `<option value="${y}">${y === 0 ? BIKES_I18N.anyYear : y}</option>`);
        yearSel.innerHTML = '<option value="">' + BIKES_I18N.chooseYear + '</option>' + opts.join('');
        yearSel.disabled = false;
    });

    function swapImage(wrapper, url) {
        let img = wrapper.querySelector('img');
        if (img) {
            img.src = url;
        } else {
            img = document.createElement('img');
            img.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#f8f9fa;';
            wrapper.querySelector('.bg-light')?.replaceWith(img);
            img.src = url;
        }
    }

    // Web search button — POSTs to the controller, swaps image on success.
    document.querySelectorAll('.refresh-image-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const origHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            try {
                const r = await fetch(btn.dataset.refreshUrl, {
                    method: 'POST',
                    headers: { 'X-CSRF-TOKEN': CSRF_TOKEN, 'Accept': 'application/json' },
                });
                const data = await r.json();
                if (data.image_url) {
                    swapImage(btn.closest('.position-relative'), data.image_url);
                    btn.innerHTML = '<i class="ri-check-line text-success"></i>';
                    setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
                } else {
                    const msg = data.error || data.message || 'No image found';
                    console.error('refresh-image server error:', msg, data);
                    btn.title = msg;
                    btn.innerHTML = '<i class="ri-error-warning-line text-danger"></i>';
                    btn.disabled = false;
                }
            } catch (e) {
                console.error('refresh-image error:', e);
                btn.innerHTML = '<i class="ri-error-warning-line text-danger"></i>';
                btn.title = String(e);
                btn.disabled = false;
            }
        });
    });

    // Upload button — sends file via FormData, swaps image on success.
    document.querySelectorAll('.upload-image-input').forEach(input => {
        input.addEventListener('change', async () => {
            if (!input.files.length) return;
            const label = document.querySelector(`label[for="${input.id}"]`);
            const origHtml = label.innerHTML;
            label.style.pointerEvents = 'none';
            label.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            const form = new FormData();
            form.append('image', input.files[0]);
            try {
                const r = await fetch(input.dataset.uploadUrl, {
                    method: 'POST',
                    headers: { 'X-CSRF-TOKEN': CSRF_TOKEN, 'Accept': 'application/json' },
                    body: form,
                });
                const data = await r.json();
                if (data.image_url) {
                    swapImage(input.closest('.position-relative'), data.image_url);
                    label.innerHTML = '<i class="ri-check-line text-success"></i>';
                    setTimeout(() => { label.innerHTML = origHtml; label.style.pointerEvents = ''; }, 2000);
                } else {
                    const msg = data.error || data.message || 'Upload failed';
                    console.error('upload-image error:', msg, data);
                    label.title = msg;
                    label.innerHTML = '<i class="ri-error-warning-line text-danger"></i>';
                    label.style.pointerEvents = '';
                }
            } catch (e) {
                console.error('upload-image error:', e);
                label.innerHTML = '<i class="ri-error-warning-line text-danger"></i>';
                label.title = String(e);
                label.style.pointerEvents = '';
            }
            input.value = '';
        });
    });

    // Poll any element marked data-sync-poll until the SyncRun reaches a terminal status.
    document.querySelectorAll('[data-sync-poll]').forEach((el) => {
        const url = el.getAttribute('data-sync-poll');
        const tick = async () => {
            try {
                const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
                if (!r.ok) return;
                const data = await r.json();
                if (data.status === 'success' || data.status === 'failed') {
                    window.location.reload();
                } else {
                    setTimeout(tick, 4000);
                }
            } catch (e) { setTimeout(tick, 6000); }
        };
        setTimeout(tick, 4000);
    });
})();
</script>
@endsection
