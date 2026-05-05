@extends('layouts.master')
@section('title', __('Watch List'))

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') {{ __('Crawler') }} @endslot
        @slot('title') {{ __('Watch List') }} @endslot
    @endcomponent

    @if (session('status'))
        <div class="alert alert-success">{{ session('status') }}</div>
    @endif

    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">{{ __('Saved searches') }}</h5>
            <p class="text-muted mb-0 fs-13">
                {{ __('Live searches you run on /parts are auto-saved here as ★ HIGH priority. Every nightly crawl re-runs them. Revoke priority to keep an entry without re-crawling.') }}
            </p>
        </div>
        <div class="card-body p-0">
            @if ($watches->isEmpty())
                <div class="text-center py-5">
                    <p class="text-muted mb-0">
                        {!! __('No saved searches yet. Run a live search on :link to add one.', [
                            'link' => '<a href="' . e(route('parts.index')) . '">' . e(__('Parts')) . '</a>',
                        ]) !!}
                    </p>
                </div>
            @else
                <table class="table mb-0">
                    <thead>
                        <tr>
                            <th>{{ __('Query') }}</th>
                            <th>{{ __('Bike scope') }}</th>
                            <th>{{ __('Priority') }}</th>
                            <th class="text-end">{{ __('Matches') }}</th>
                            <th>{{ __('Last crawled') }}</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($watches as $w)
                            @php($cat = $w->bike_catalog_id ? $catalogs->get($w->bike_catalog_id) : null)
                            <tr>
                                <td>
                                    <a href="{{ route('parts.index', ['q' => $w->query]) }}" class="fw-medium">
                                        {{ $w->query }}
                                    </a>
                                </td>
                                <td>
                                    @if ($cat)
                                        {{ $cat->displayLabel() }}
                                    @else
                                        <span class="text-muted">{{ __('Any of my bikes') }}</span>
                                    @endif
                                </td>
                                <td>
                                    @if ($w->is_high_priority)
                                        <span class="badge bg-warning-subtle text-warning">{{ __('★ HIGH') }}</span>
                                    @else
                                        <span class="badge bg-secondary-subtle text-muted">{{ __('tracked') }}</span>
                                    @endif
                                </td>
                                <td class="text-end">{{ $w->match_count }}</td>
                                <td>
                                    {{ $w->last_crawled_at?->diffForHumans() ?? '—' }}
                                </td>
                                <td class="text-end">
                                    <form method="POST" action="{{ route('watch-list.priority', $w) }}" class="d-inline">
                                        @csrf @method('PATCH')
                                        <button type="submit" class="btn btn-sm btn-outline-secondary">
                                            {{ $w->is_high_priority ? __('Revoke priority') : __('Promote') }}
                                        </button>
                                    </form>
                                    <form method="POST" action="{{ route('watch-list.destroy', $w) }}" class="d-inline ms-1">
                                        @csrf @method('DELETE')
                                        <button type="submit" class="btn btn-sm btn-outline-danger"
                                                onclick="return confirm('{{ __('Remove this watch?') }}')">
                                            {{ __('Remove') }}
                                        </button>
                                    </form>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            @endif
        </div>
    </div>
@endsection
