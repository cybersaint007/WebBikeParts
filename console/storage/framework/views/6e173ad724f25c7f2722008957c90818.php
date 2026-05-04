<?php $__env->startSection('title', 'Parts'); ?>

<?php $__env->startSection('content'); ?>
    <?php $__env->startComponent('components.breadcrumb'); ?>
        <?php $__env->slot('li_1'); ?> Crawler <?php $__env->endSlot(); ?>
        <?php $__env->slot('title'); ?> Parts <?php $__env->endSlot(); ?>
    <?php echo $__env->renderComponent(); ?>

    <div class="alert alert-info d-flex align-items-center">
        <div class="flex-grow-1">
            <?php if($scope['all_bikes']): ?>
                <strong>Showing parts for: all crawled bikes</strong>
                <?php if($scope['my_bike_count'] > 0): ?>
                    — <a href="<?php echo e(route('parts.index', request()->except('all_bikes'))); ?>">Limit to my bikes</a>
                <?php endif; ?>
            <?php elseif($scope['my_bike_count'] === 0): ?>
                <strong>You haven't added any bikes yet.</strong>
                <a href="<?php echo e(route('my-bikes.index')); ?>">Add a bike</a> to start crawling, or
                <a href="<?php echo e(route('parts.index', array_merge(request()->all(), ['all_bikes' => 1]))); ?>">browse all bikes</a>.
            <?php else: ?>
                <strong>Showing parts for: My Bikes (<?php echo e($scope['my_bike_count']); ?>)</strong>
                <span class="text-muted">— <?php echo e(implode(', ', $scope['my_bike_labels'])); ?></span>
                — <a href="<?php echo e(route('parts.index', array_merge(request()->all(), ['all_bikes' => 1]))); ?>">Show all bikes</a>
            <?php endif; ?>
        </div>
    </div>

    <div class="row">
        
        <div class="col-xl-3 col-lg-4">
            <div class="card">
                <div class="card-header">
                    <div class="d-flex align-items-center">
                        <h5 class="fs-16 flex-grow-1 mb-0">Filters</h5>
                        <a href="<?php echo e(route('parts.index')); ?>" class="text-decoration-underline">Clear all</a>
                    </div>
                </div>

                <div class="card-body">
                    <form method="GET" action="<?php echo e(route('parts.index')); ?>">
                        <div class="mb-3">
                            <label class="form-label fw-medium">Search</label>
                            <input type="search" name="q" value="<?php echo e(request('q')); ?>" class="form-control"
                                   placeholder="Title, part #, fitment…">
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Category</label>
                            <select name="category" class="form-select">
                                <option value="">All categories</option>
                                <?php $__currentLoopData = $facets['categories']; $__env->addLoop($__currentLoopData); foreach($__currentLoopData as $cat): $__env->incrementLoopIndices(); $loop = $__env->getLastLoop(); ?>
                                    <option value="<?php echo e($cat); ?>" <?php if(request('category') === $cat): echo 'selected'; endif; ?>><?php echo e($cat); ?></option>
                                <?php endforeach; $__env->popLoop(); $loop = $__env->getLastLoop(); ?>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Source</label>
                            <select name="source" class="form-select">
                                <option value="">All sources</option>
                                <?php $__currentLoopData = $facets['sources']; $__env->addLoop($__currentLoopData); foreach($__currentLoopData as $src): $__env->incrementLoopIndices(); $loop = $__env->getLastLoop(); ?>
                                    <option value="<?php echo e($src); ?>" <?php if(request('source') === $src): echo 'selected'; endif; ?>><?php echo e($src); ?></option>
                                <?php endforeach; $__env->popLoop(); $loop = $__env->getLastLoop(); ?>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Condition</label>
                            <select name="condition" class="form-select">
                                <option value="">Any condition</option>
                                <?php $__currentLoopData = $facets['conditions']; $__env->addLoop($__currentLoopData); foreach($__currentLoopData as $cond): $__env->incrementLoopIndices(); $loop = $__env->getLastLoop(); ?>
                                    <option value="<?php echo e($cond); ?>" <?php if(request('condition') === $cond): echo 'selected'; endif; ?>><?php echo e($cond); ?></option>
                                <?php endforeach; $__env->popLoop(); $loop = $__env->getLastLoop(); ?>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">Price range</label>
                            <div class="d-flex gap-2">
                                <input type="number" step="0.01" name="price_min" value="<?php echo e(request('price_min')); ?>"
                                       class="form-control" placeholder="Min">
                                <input type="number" step="0.01" name="price_max" value="<?php echo e(request('price_max')); ?>"
                                       class="form-control" placeholder="Max">
                            </div>
                        </div>

                        <button type="submit" class="btn btn-primary w-100">Apply filters</button>
                    </form>
                </div>
            </div>
        </div>

        
        <div class="col-xl-9 col-lg-8">
            <div class="card">
                <div class="card-header">
                    <div class="d-flex flex-wrap align-items-center gap-2">
                        <input id="parts-q" type="search" class="form-control flex-grow-1"
                               style="max-width:380px"
                               placeholder="Instant search: title, part #, fitment…"
                               value="<?php echo e(request('q')); ?>">
                        <h5 class="card-title mb-0 ms-auto" id="parts-result-count">
                            Showing <?php echo e($listings->firstItem() ?? 0); ?>–<?php echo e($listings->lastItem() ?? 0); ?>

                            of <?php echo e($listings->total()); ?> parts
                        </h5>
                    </div>
                </div>

                <div class="card-body" id="parts-grid-container">
                    <?php if($listings->isEmpty()): ?>
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
                    <?php else: ?>
                        <div class="row" id="parts-grid">
                            <?php $__currentLoopData = $listings; $__env->addLoop($__currentLoopData); foreach($__currentLoopData as $l): $__env->incrementLoopIndices(); $loop = $__env->getLastLoop(); ?>
                                <div class="col-xl-4 col-md-6">
                                    <div class="card h-100 shadow-none border">
                                        <div class="bg-light text-center" style="height:180px; overflow:hidden;">
                                            <?php if($l->image_url): ?>
                                                <img src="<?php echo e($l->image_url); ?>" alt=""
                                                     style="max-height:180px; object-fit:contain;"
                                                     loading="lazy"
                                                     onerror="this.style.display='none'">
                                            <?php else: ?>
                                                <div class="d-flex align-items-center justify-content-center h-100 text-muted">
                                                    <i class="ri-image-line" style="font-size:3rem;"></i>
                                                </div>
                                            <?php endif; ?>
                                        </div>
                                        <div class="card-body">
                                            <a href="<?php echo e(route('parts.show', $l)); ?>" class="text-body">
                                                <h6 class="mb-2 text-truncate-two-lines" title="<?php echo e($l->title); ?>">
                                                    <?php echo e(\Illuminate\Support\Str::limit($l->title, 80)); ?>

                                                </h6>
                                            </a>
                                            <?php if(!empty($bikeLabels[$l->bike_key] ?? null)): ?>
                                                <p class="text-muted fs-12 mb-2 mb-0" title="<?php echo e($l->bike_key); ?>">
                                                    <i class="ri-motorbike-line me-1"></i><?php echo e($bikeLabels[$l->bike_key]); ?>

                                                </p>
                                            <?php endif; ?>
                                            <div class="d-flex gap-1 flex-wrap mb-2">
                                                <span class="badge bg-light text-muted"><?php echo e($l->source_name); ?></span>
                                                <?php if($l->condition): ?>
                                                    <span class="badge bg-info-subtle text-info"><?php echo e($l->condition); ?></span>
                                                <?php endif; ?>
                                                <?php if($l->category && $l->category !== 'unknown'): ?>
                                                    <span class="badge bg-secondary-subtle text-secondary"><?php echo e($l->category); ?></span>
                                                <?php endif; ?>
                                                <?php
                                                    $hay = mb_strtolower(($l->title ?? '') . ' ' . ($l->description ?? ''));
                                                    $watched = false;
                                                    foreach ($watchQueries as $q) {
                                                        if ($q !== '' && str_contains($hay, $q)) { $watched = true; break; }
                                                    }
                                                ?>
                                                <?php if($watched): ?>
                                                    <span class="badge bg-warning-subtle text-warning" title="Matches an active watch">
                                                        ★ Watched
                                                    </span>
                                                <?php endif; ?>
                                            </div>
                                            <div class="d-flex align-items-center mb-3">
                                                <h5 class="mb-0 me-2">
                                                    <?php if($l->price_amount !== null): ?>
                                                        <?php echo e(number_format((float) $l->price_amount, 2)); ?>

                                                        <small class="text-muted fs-13"><?php echo e($l->price_currency); ?></small>
                                                    <?php else: ?>
                                                        <span class="text-muted fs-14">Price n/a</span>
                                                    <?php endif; ?>
                                                </h5>
                                            </div>
                                            <a href="<?php echo e($l->url); ?>" target="_blank" rel="noopener noreferrer"
                                               class="btn btn-sm btn-outline-primary w-100">
                                                View on <?php echo e($l->source_name); ?>

                                                <i class="ri-external-link-line ms-1"></i>
                                            </a>
                                            <p class="text-muted fs-12 mt-2 mb-0">
                                                Last seen <?php echo e($l->last_seen_at?->diffForHumans()); ?>

                                            </p>
                                        </div>
                                    </div>
                                </div>
                            <?php endforeach; $__env->popLoop(); $loop = $__env->getLastLoop(); ?>
                        </div>

                        <div class="mt-3" id="parts-pagination">
                            <?php echo e($listings->links()); ?>

                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </div>
<?php $__env->stopSection(); ?>

<?php $__env->startSection('script'); ?>
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
        formData.append('_token', document.querySelector('meta[name="csrf-token"]')?.content || '<?php echo e(csrf_token()); ?>');
        formData.append('q', q);
        const r = await fetch('<?php echo e(route("parts.live-search")); ?>', {
            method: 'POST',
            headers: { 'Accept': 'application/json', 'X-CSRF-TOKEN': '<?php echo e(csrf_token()); ?>' },
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
<?php $__env->stopSection(); ?>

<?php echo $__env->make('layouts.master', array_diff_key(get_defined_vars(), ['__data' => 1, '__path' => 1]))->render(); ?><?php /**PATH /Users/cybersaint/Sites/WebCrawler/console/resources/views/parts/index.blade.php ENDPATH**/ ?>