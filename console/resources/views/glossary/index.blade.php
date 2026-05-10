@extends('layouts.master')
@section('title', __('Parts Glossary'))

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') {{ __('Crawler') }} @endslot
        @slot('title') {{ __('Parts Glossary') }} @endslot
    @endcomponent

    @if (session('success'))
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            {{ session('success') }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    @endif

    @if ($errors->any())
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            {{ $errors->first() }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    @endif

    <div class="card">
        <div class="card-header d-flex flex-wrap align-items-center gap-2">
            <input id="glossary-q" type="search" class="form-control flex-grow-1"
                   style="max-width:380px"
                   placeholder="{{ __('Search parts in English, 繁中, or 日本語…') }}">
            <span class="text-muted fs-13 ms-1" id="glossary-count">
                {{ $grouped->flatten()->count() }} {{ __('terms') }}
            </span>
            <button type="button" class="btn btn-primary ms-auto"
                    data-bs-toggle="modal" data-bs-target="#addTermModal">
                <i class="ri-add-line me-1"></i>{{ __('Add term') }}
            </button>
        </div>

        <div class="card-body p-0" id="glossary-body">
            {{-- Category accordion (default state) --}}
            <div class="accordion accordion-flush" id="glossaryAccordion">
                @foreach ($categories as $cat)
                    @php($items = $grouped->get($cat, collect()))
                    @if ($items->isNotEmpty())
                    <div class="accordion-item" data-category="{{ $cat }}">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed fw-semibold text-capitalize py-2"
                                    type="button"
                                    data-bs-toggle="collapse"
                                    data-bs-target="#cat-{{ $cat }}"
                                    aria-expanded="false">
                                {{ __($cat) }}
                                <span class="badge bg-secondary-subtle text-secondary ms-2">{{ $items->count() }}</span>
                            </button>
                        </h2>
                        <div id="cat-{{ $cat }}" class="accordion-collapse collapse">
                            <div class="accordion-body p-0">
                                <table class="table table-sm table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th>{{ __('English') }}</th>
                                            <th>繁中</th>
                                            <th>日本語</th>
                                            <th class="d-none d-md-table-cell text-muted fw-normal fs-12">{{ __('Notes') }}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        @foreach ($items->sortBy('term_en') as $entry)
                                        <tr>
                                            <td>
                                                {{ $entry->term_en }}
                                                @if ($entry->source === 'user')
                                                    <i class="ri-user-line text-muted fs-11 ms-1" title="{{ __('User contributed') }}"></i>
                                                @endif
                                            </td>
                                            <td>
                                                @if ($entry->term_zh)
                                                    {{ $entry->term_zh }}
                                                @else
                                                    <span class="badge bg-secondary-subtle text-secondary">—</span>
                                                @endif
                                            </td>
                                            <td>
                                                @if ($entry->term_ja)
                                                    {{ $entry->term_ja }}
                                                @else
                                                    <span class="badge bg-secondary-subtle text-secondary">—</span>
                                                @endif
                                            </td>
                                            <td class="d-none d-md-table-cell text-muted fs-12">{{ $entry->notes }}</td>
                                        </tr>
                                        @endforeach
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    @endif
                @endforeach
            </div>

            {{-- Search results area (hidden by default, shown when query active) --}}
            <div id="glossary-results" class="d-none">
                <table class="table table-sm table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>{{ __('English') }}</th>
                            <th>繁中</th>
                            <th>日本語</th>
                            <th>{{ __('Category') }}</th>
                        </tr>
                    </thead>
                    <tbody id="glossary-results-body"></tbody>
                </table>
                <div id="glossary-no-results" class="d-none text-center py-5">
                    <p class="text-muted">{{ __('No results for ":query"', [':query' => '']) }}</p>
                </div>
            </div>
        </div>
    </div>

    {{-- Add Term Modal --}}
    <div class="modal fade" id="addTermModal" tabindex="-1" aria-labelledby="addTermModalLabel">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <form method="POST" action="{{ route('glossary.store') }}">
                    @csrf
                    <div class="modal-header">
                        <h5 class="modal-title" id="addTermModalLabel">{{ __('Add term') }}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted fs-13">
                            {{ __('Enter the part name in at least one language. Missing translations will be auto-filled by AI if configured.') }}
                        </p>
                        <div class="mb-3">
                            <label class="form-label">English</label>
                            <input type="text" name="term_en" class="form-control @error('term_en') is-invalid @enderror"
                                   value="{{ old('term_en') }}" placeholder="e.g. fork bushing">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">繁體中文</label>
                            <input type="text" name="term_zh" class="form-control"
                                   value="{{ old('term_zh') }}" placeholder="e.g. 前叉襯套">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">日本語</label>
                            <input type="text" name="term_ja" class="form-control"
                                   value="{{ old('term_ja') }}" placeholder="e.g. フォークブッシュ">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">{{ __('Category') }} <span class="text-danger">*</span></label>
                            <select name="category" class="form-select" required>
                                @foreach ($categories as $cat)
                                    <option value="{{ $cat }}" {{ old('category') === $cat ? 'selected' : '' }}>
                                        {{ ucfirst($cat) }}
                                    </option>
                                @endforeach
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">{{ __('Notes') }} <span class="text-muted fs-12">({{ __('optional') }})</span></label>
                            <textarea name="notes" class="form-control" rows="2"
                                      placeholder="{{ __('Optional notes, synonyms, or context') }}">{{ old('notes') }}</textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-light" data-bs-dismiss="modal">{{ __('Cancel') }}</button>
                        <button type="submit" class="btn btn-primary">{{ __('Save term') }}</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
@endsection

@section('script')
<script>
(function () {
    const qInput     = document.getElementById('glossary-q');
    const accordion  = document.getElementById('glossaryAccordion');
    const resultsDiv = document.getElementById('glossary-results');
    const resultsBody= document.getElementById('glossary-results-body');
    const noResults  = document.getElementById('glossary-no-results');
    const countEl    = document.getElementById('glossary-count');

    function escapeHtml(s) {
        if (!s) return '';
        return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    let timer;
    qInput.addEventListener('input', () => {
        clearTimeout(timer);
        const q = qInput.value.trim();
        if (q.length < 1) {
            accordion.classList.remove('d-none');
            resultsDiv.classList.add('d-none');
            countEl.textContent = '';
            return;
        }
        timer = setTimeout(async () => {
            try {
                const r = await fetch('{{ route("glossary.search") }}?q=' + encodeURIComponent(q),
                    { headers: { 'Accept': 'application/json' } });
                if (!r.ok) return;
                const items = await r.json();

                accordion.classList.add('d-none');
                resultsDiv.classList.remove('d-none');

                if (items.length === 0) {
                    resultsBody.innerHTML = '';
                    noResults.classList.remove('d-none');
                    countEl.textContent = '0 {{ __("terms") }}';
                    return;
                }

                noResults.classList.add('d-none');
                countEl.textContent = items.length + ' {{ __("terms") }}';
                resultsBody.innerHTML = items.map(t => `
                    <tr>
                        <td>${escapeHtml(t.term_en)}${t.source === 'user' ? ' <i class="ri-user-line text-muted fs-11"></i>' : ''}</td>
                        <td>${t.term_zh ? escapeHtml(t.term_zh) : '<span class="badge bg-secondary-subtle text-secondary">—</span>'}</td>
                        <td>${t.term_ja ? escapeHtml(t.term_ja) : '<span class="badge bg-secondary-subtle text-secondary">—</span>'}</td>
                        <td><span class="badge bg-light text-dark text-capitalize">${escapeHtml(t.category)}</span></td>
                    </tr>`).join('');
            } catch (e) { /* ignore */ }
        }, 250);
    });

    // Reopen modal if validation failed
    @if ($errors->any())
    const modal = new bootstrap.Modal(document.getElementById('addTermModal'));
    modal.show();
    @endif
})();
</script>
@endsection
