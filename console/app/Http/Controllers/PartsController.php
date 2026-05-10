<?php

namespace App\Http\Controllers;

use App\Jobs\LiveSearchJob;
use App\Models\PartsWatch;
use App\Models\SyncRun;
use App\Models\Watcher\BikeCatalog;
use App\Models\Watcher\Listing;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class PartsController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function index(Request $request)
    {
        $user = $request->user();
        $myCatalogIds = $user->selectedCatalogBikeIds();
        $myBikeKeys = BikeCatalog::query()->whereIn('id', $myCatalogIds)->pluck('catalog_key')->all();
        $allBikes = $request->boolean('all_bikes');
        $selectedBike = $request->input('bike') ?: null;

        $query = Listing::query()
            ->category($request->input('category'))
            ->subcategory($request->input('subcategory'))
            ->source($request->input('source'))
            ->condition($request->input('condition'))
            ->priceBetween($request->input('price_min'), $request->input('price_max'))
            ->search($request->input('q'));

        if ($selectedBike) {
            $query->forBikeKeys([$selectedBike]);
        } elseif (!$allBikes) {
            $query->forBikeKeys($myBikeKeys);
        }

        $listings = $query->orderByDesc('last_seen_at')->paginate(24)->withQueryString();

        $pageBikeKeys = collect($listings->items())->pluck('bike_key')->filter()->unique()->all();
        $bikeLabels = BikeCatalog::query()
            ->whereIn('catalog_key', $pageBikeKeys)
            ->get()
            ->mapWithKeys(fn ($c) => [$c->catalog_key => $c->displayLabel()])
            ->all();

        $bikeOptionQuery = BikeCatalog::query();
        if ($allBikes) {
            $bikeOptionQuery->whereIn('catalog_key', Listing::query()->select('bike_key')->distinct());
        } else {
            $bikeOptionQuery->whereIn('id', $myCatalogIds);
        }
        $bikeOptions = $bikeOptionQuery
            ->orderBy('make')->orderBy('model')->orderBy('year_start')
            ->get()
            ->map(fn ($c) => ['key' => $c->catalog_key, 'label' => $c->displayLabel()])
            ->values()
            ->all();

        // Preserve the currently-selected bike in the dropdown even if scope changed.
        if ($selectedBike && !collect($bikeOptions)->contains('key', $selectedBike)) {
            $fallback = BikeCatalog::query()->where('catalog_key', $selectedBike)->first();
            if ($fallback) {
                array_unshift($bikeOptions, ['key' => $fallback->catalog_key, 'label' => $fallback->displayLabel()]);
            }
        }

        $facets = [
            'categories'    => Listing::query()->select('category')->distinct()->orderBy('category')->pluck('category'),
            'subcategories' => Listing::query()->select('subcategory')->whereNotNull('subcategory')->distinct()->orderBy('subcategory')->pluck('subcategory'),
            'sources'       => Listing::query()->select('source_name')->distinct()->orderBy('source_name')->pluck('source_name'),
            'conditions'    => Listing::query()->select('condition')->whereNotNull('condition')->distinct()->orderBy('condition')->pluck('condition'),
            'bikes'         => $bikeOptions,
        ];

        $scope = [
            'all_bikes'      => $allBikes,
            'my_bike_count'  => count($myBikeKeys),
            'my_bike_labels' => BikeCatalog::query()->whereIn('id', $myCatalogIds)->orderBy('make')->orderBy('model')->get()
                                  ->map(fn ($c) => $c->displayLabel())->all(),
        ];

        // Always the user's own bikes — used to populate the live-search bike selector.
        $myBikeOptions = BikeCatalog::query()
            ->whereIn('id', $myCatalogIds)
            ->orderBy('make')->orderBy('model')->orderBy('year_start')
            ->get()
            ->map(fn ($c) => ['key' => $c->catalog_key, 'label' => $c->displayLabel()])
            ->values()
            ->all();

        // Active high-priority watch queries — used to flag matching listings with a ★ badge.
        $watchQueries = $user->partsWatches()
            ->where('is_high_priority', true)
            ->pluck('query')
            ->map(fn ($q) => mb_strtolower($q))
            ->unique()
            ->values()
            ->all();

        return view('parts.index', compact('listings', 'facets', 'scope', 'watchQueries', 'bikeLabels', 'myBikeOptions'));
    }

    public function show(Listing $listing)
    {
        $listing->load(['snapshots' => fn ($q) => $q->orderByDesc('checked_at')->limit(50)]);
        return view('parts.show', compact('listing'));
    }

    public function searchJson(Request $request): JsonResponse
    {
        $user = $request->user();
        $myCatalogIds = $user->selectedCatalogBikeIds();
        $myBikeKeys = BikeCatalog::query()->whereIn('id', $myCatalogIds)->pluck('catalog_key')->all();
        $allBikes = $request->boolean('all_bikes');
        $selectedBike = $request->input('bike') ?: null;

        $query = Listing::query()
            ->category($request->input('category'))
            ->subcategory($request->input('subcategory'))
            ->source($request->input('source'))
            ->condition($request->input('condition'))
            ->priceBetween($request->input('price_min'), $request->input('price_max'))
            ->search($request->input('q'));

        if ($selectedBike) {
            $query->forBikeKeys([$selectedBike]);
        } elseif (!$allBikes) {
            $query->forBikeKeys($myBikeKeys);
        }

        $listings = $query->orderByDesc('last_seen_at')->paginate(24)->withQueryString();

        $pageBikeKeys = collect($listings->items())->pluck('bike_key')->filter()->unique()->all();
        $bikeLabels = BikeCatalog::query()
            ->whereIn('catalog_key', $pageBikeKeys)
            ->get()
            ->mapWithKeys(fn ($c) => [$c->catalog_key => $c->displayLabel()])
            ->all();

        return response()->json([
            'total' => $listings->total(),
            'data' => $listings->items() ? array_map(fn ($l) => [
                'id' => $l->id,
                'title' => $l->title,
                'image_url' => $l->image_url,
                'source_name' => $l->source_name,
                'condition' => $l->condition,
                'category' => $l->category,
                'bike_key' => $l->bike_key,
                'bike_label' => $bikeLabels[$l->bike_key] ?? $l->bike_key,
                'price_amount' => $l->price_amount,
                'price_currency' => $l->price_currency,
                'last_seen_at' => $l->last_seen_at?->toIso8601String(),
                'last_seen_human' => $l->last_seen_at?->diffForHumans(),
                'url' => $l->url,
                'show_url' => route('parts.show', $l),
            ], $listings->items()) : [],
            'pagination' => [
                'current_page' => $listings->currentPage(),
                'last_page' => $listings->lastPage(),
                'first_item' => $listings->firstItem(),
                'last_item' => $listings->lastItem(),
            ],
        ]);
    }

    public function liveSearch(Request $request): JsonResponse
    {
        $data = $request->validate([
            'q'        => ['required', 'string', 'min:2', 'max:200'],
            'bike_key' => ['nullable', 'string', 'max:200'],
        ]);

        $user = $request->user();
        $myCatalogIds = $user->selectedCatalogBikeIds();
        $bikeKey = $data['bike_key'] ?? null;

        if ($bikeKey) {
            $myCatalogs = BikeCatalog::query()
                ->whereIn('id', $myCatalogIds)
                ->where('catalog_key', $bikeKey)
                ->get();
            // Silently fall back to all bikes if the requested key isn't in the user's list.
            if ($myCatalogs->isEmpty()) {
                $myCatalogs = BikeCatalog::query()->whereIn('id', $myCatalogIds)->get();
            }
        } else {
            $myCatalogs = BikeCatalog::query()
                ->whereIn('id', $myCatalogIds)
                ->get();
        }

        $watchIds = DB::transaction(function () use ($user, $myCatalogs, $data) {
            $ids = [];
            // For each of the user's bikes, create or re-promote a high-priority watch entry.
            // If the user has no bikes, we still create a global (bike_catalog_id=null) watch.
            $targets = $myCatalogs->isEmpty()
                ? collect([null])
                : $myCatalogs->pluck('id');

            foreach ($targets as $bikeId) {
                $watch = PartsWatch::firstOrNew([
                    'user_id' => $user->id,
                    'bike_catalog_id' => $bikeId,
                    'query' => $data['q'],
                ]);
                $watch->is_high_priority = true;
                $watch->priority_revoked_at = null;
                if (!$watch->exists) {
                    $watch->match_count = 0;
                }
                $watch->save();
                $ids[] = $watch->id;
            }
            return $ids;
        });

        $run = SyncRun::create([
            'kind' => SyncRun::KIND_LIVE_SEARCH,
            'status' => SyncRun::STATUS_QUEUED,
            'triggered_by' => $user->id,
            'payload' => [
                'q' => $data['q'],
                'catalog_keys' => $myCatalogs->pluck('catalog_key')->all(),
                'watch_ids' => $watchIds,
            ],
        ]);

        LiveSearchJob::dispatch(
            $run->id,
            $data['q'],
            $myCatalogs->pluck('catalog_key')->all(),
        )->onQueue('sync');

        return response()->json([
            'run_id' => $run->id,
            'status_url' => route('sync.show', $run),
            'watch_ids' => $watchIds,
        ]);
    }
}
