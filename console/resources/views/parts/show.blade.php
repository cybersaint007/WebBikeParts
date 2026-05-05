@extends('layouts.master')
@section('title', $listing->title)

@section('content')
    @component('components.breadcrumb')
        @slot('li_1')
            <a href="{{ route('parts.index') }}">{{ __('Parts') }}</a>
        @endslot
        @slot('title') {{ \Illuminate\Support\Str::limit($listing->title, 60) }} @endslot
    @endcomponent

    <div class="row">
        <div class="col-lg-5">
            <div class="card">
                <div class="card-body bg-light text-center" style="min-height:400px;">
                    @if ($listing->image_url)
                        <img src="{{ $listing->image_url }}" alt="" style="max-width:100%; max-height:380px; object-fit:contain;"
                             onerror="this.style.display='none'">
                    @else
                        <div class="d-flex align-items-center justify-content-center" style="height:380px;">
                            <i class="ri-image-line text-muted" style="font-size:6rem;"></i>
                        </div>
                    @endif
                </div>
            </div>
        </div>

        <div class="col-lg-7">
            <div class="card">
                <div class="card-body">
                    <h4 class="mb-3">{{ $listing->title }}</h4>

                    <div class="d-flex gap-2 flex-wrap mb-3">
                        <span class="badge bg-light text-muted">{{ $listing->source_name }}</span>
                        @if ($listing->condition)
                            <span class="badge bg-info-subtle text-info">{{ $listing->condition }}</span>
                        @endif
                        @if ($listing->category && $listing->category !== 'unknown')
                            <span class="badge bg-secondary-subtle text-secondary">{{ $listing->category }}</span>
                        @endif
                        <span class="badge bg-warning-subtle text-warning">{{ __('bike: :key', ['key' => $listing->bike_key]) }}</span>
                    </div>

                    <h2 class="mb-4">
                        @if ($listing->price_amount !== null)
                            {{ number_format((float) $listing->price_amount, 2) }}
                            <small class="text-muted fs-16">{{ $listing->price_currency }}</small>
                            @if ($listing->shipping_amount)
                                <small class="text-muted fs-13 d-block">+ {{ number_format((float) $listing->shipping_amount, 2) }} {{ __('shipping') }}</small>
                            @endif
                        @else
                            <span class="text-muted fs-18">{{ __('Price not available') }}</span>
                        @endif
                    </h2>

                    <a href="{{ $listing->url }}" target="_blank" rel="noopener noreferrer"
                       class="btn btn-primary btn-lg mb-4">
                        {{ __('View on :source', ['source' => $listing->source_name]) }}
                        <i class="ri-external-link-line ms-1"></i>
                    </a>

                    <dl class="row mb-0">
                        @if ($listing->seller_name)
                            <dt class="col-sm-3 text-muted">{{ __('Seller') }}</dt>
                            <dd class="col-sm-9">{{ $listing->seller_name }}{{ $listing->seller_country ? ' · ' . $listing->seller_country : '' }}</dd>
                        @endif
                        @if ($listing->part_number)
                            <dt class="col-sm-3 text-muted">{{ __('Part #') }}</dt>
                            <dd class="col-sm-9"><code>{{ $listing->part_number }}</code></dd>
                        @endif
                        <dt class="col-sm-3 text-muted">{{ __('First seen') }}</dt>
                        <dd class="col-sm-9">{{ $listing->first_seen_at?->format('Y-m-d H:i') }}</dd>
                        <dt class="col-sm-3 text-muted">{{ __('Last seen') }}</dt>
                        <dd class="col-sm-9">{{ $listing->last_seen_at?->format('Y-m-d H:i') }} ({{ $listing->last_seen_at?->diffForHumans() }})</dd>
                    </dl>
                </div>
            </div>
        </div>
    </div>

    @if ($listing->description)
        <div class="card">
            <div class="card-header"><h5 class="mb-0">{{ __('Description') }}</h5></div>
            <div class="card-body" style="white-space:pre-wrap;">{{ $listing->description }}</div>
        </div>
    @endif

    @if ($listing->fitment_text)
        <div class="card">
            <div class="card-header"><h5 class="mb-0">{{ __('Fitment') }}</h5></div>
            <div class="card-body" style="white-space:pre-wrap;">{{ $listing->fitment_text }}</div>
        </div>
    @endif

    @if ($listing->snapshots->isNotEmpty())
        <div class="card">
            <div class="card-header"><h5 class="mb-0">{{ __('Price history') }}</h5></div>
            <div class="card-body p-0">
                <table class="table mb-0">
                    <thead><tr><th>{{ __('Checked') }}</th><th class="text-end">{{ __('Price') }}</th><th>{{ __('Availability') }}</th></tr></thead>
                    <tbody>
                    @foreach ($listing->snapshots as $s)
                        <tr>
                            <td>{{ $s->checked_at?->format('Y-m-d H:i') }}</td>
                            <td class="text-end">
                                @if ($s->price_amount !== null)
                                    {{ number_format((float) $s->price_amount, 2) }} {{ $listing->price_currency }}
                                @else
                                    <span class="text-muted">—</span>
                                @endif
                            </td>
                            <td>{{ $s->availability_status ?? '—' }}</td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif
@endsection
