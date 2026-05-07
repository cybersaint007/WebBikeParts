<?php

namespace App\Http\Controllers;

use App\Models\PartsWatch;
use App\Models\SyncRun;
use App\Models\Watcher\BikeCatalog;
use App\Models\Watcher\Listing;
use Illuminate\Support\Facades\DB;

class DashboardController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function index()
    {
        $user        = auth()->user();
        $catalogIds  = $user->selectedCatalogBikeIds();
        $catalogKeys = BikeCatalog::whereIn('id', $catalogIds)->pluck('catalog_key')->all();

        $bikesCount   = count($catalogIds);
        $partsCount   = empty($catalogKeys) ? 0 : Listing::forBikeKeys($catalogKeys)->count();
        $watchesCount = PartsWatch::where('user_id', $user->id)->where('is_high_priority', true)->count();
        $newThisWeek  = empty($catalogKeys) ? 0 : Listing::forBikeKeys($catalogKeys)->where('last_seen_at', '>=', now()->subDays(7))->count();

        // Bikes grid (up to 6)
        $userBikes  = $user->userBikes()->orderByDesc('created_at')->take(6)->get();
        $totalBikes = $bikesCount;
        $bikeIds    = $userBikes->pluck('bike_catalog_id')->all();
        $catalogs   = empty($bikeIds) ? collect() : BikeCatalog::whereIn('id', $bikeIds)->get()->keyBy('id');

        // Latest crawl-bike run per catalog_key (reuse MyBikesController pattern)
        $shownKeys  = $catalogs->pluck('catalog_key')->filter()->all();
        $latestRuns = collect();
        if (!empty($shownKeys)) {
            $latestRuns = SyncRun::where('kind', SyncRun::KIND_CRAWL_BIKE)
                ->orderByDesc('id')
                ->limit(100)
                ->get()
                ->filter(fn ($r) => in_array($r->payload['catalog_key'] ?? null, $shownKeys, true))
                ->groupBy(fn ($r) => $r->payload['catalog_key'])
                ->map(fn ($g) => $g->first());
        }

        // Watch summary (top 5 by match_count)
        $topWatches   = PartsWatch::where('user_id', $user->id)->orderByDesc('match_count')->take(5)->get();
        $watchBikeIds = $topWatches->pluck('bike_catalog_id')->filter()->unique()->values()->all();
        $watchBikes   = empty($watchBikeIds) ? collect() : BikeCatalog::whereIn('id', $watchBikeIds)->get()->keyBy('id');

        // Recent sync activity (last 5)
        $recentSyncs = SyncRun::latest('id')->take(5)->get();

        // Admin: crawler queue health
        $jobStats = null;
        if ($user->isAdmin()) {
            $jobStats = DB::connection('pgsql_watcher')
                ->table('crawl_jobs')
                ->selectRaw('status, count(*) as cnt')
                ->groupBy('status')
                ->get()
                ->pluck('cnt', 'status');
        }

        return view('dashboard.index', compact(
            'bikesCount', 'partsCount', 'watchesCount', 'newThisWeek',
            'userBikes', 'totalBikes', 'catalogs', 'latestRuns',
            'topWatches', 'watchBikes',
            'recentSyncs',
            'jobStats'
        ));
    }
}
