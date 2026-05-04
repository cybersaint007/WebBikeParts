<?php

namespace App\Http\Controllers;

use App\Jobs\CrawlBikeJob;
use App\Models\SyncRun;
use App\Models\UserBike;
use App\Models\Watcher\BikeCatalog;
use Illuminate\Http\Request;

class MyBikesController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function index()
    {
        $userBikes = auth()->user()->userBikes()->orderByDesc('created_at')->get();
        $catalogIds = $userBikes->pluck('bike_catalog_id')->all();
        $catalogs = BikeCatalog::query()->whereIn('id', $catalogIds)->get()->keyBy('id');
        $makes = BikeCatalog::availableMakes();

        // Pull the latest crawl-bike SyncRun per catalog_key so the bike card can show a status pill.
        $catalogKeys = $catalogs->pluck('catalog_key')->filter()->all();
        $latestRuns = collect();
        if (!empty($catalogKeys)) {
            $latestRuns = SyncRun::query()
                ->where('kind', SyncRun::KIND_CRAWL_BIKE)
                ->orderByDesc('id')
                ->limit(200)
                ->get()
                ->filter(fn ($r) => in_array($r->payload['catalog_key'] ?? null, $catalogKeys, true))
                ->groupBy(fn ($r) => $r->payload['catalog_key'])
                ->map(fn ($group) => $group->first()); // first = newest after orderByDesc
        }

        // Latest catalog sync (any user / cron) for the "last updated" line and button state.
        $latestCatalog = SyncRun::query()
            ->where('kind', SyncRun::KIND_CATALOG)
            ->latest('id')
            ->first();
        $catalogInflight = SyncRun::query()
            ->where('kind', SyncRun::KIND_CATALOG)
            ->whereIn('status', [SyncRun::STATUS_QUEUED, SyncRun::STATUS_RUNNING])
            ->latest('id')
            ->first();

        return view('my-bikes.index', compact(
            'userBikes', 'catalogs', 'makes',
            'latestRuns', 'latestCatalog', 'catalogInflight'
        ));
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'make' => ['required', 'string', 'max:50'],
            'model_slug' => ['required', 'string', 'max:150'],
            // 0 means "any year" (catalog row didn't have year info from webike).
            'year' => ['required', 'integer', 'min:0', 'max:2100'],
            'nickname' => ['nullable', 'string', 'max:120'],
        ]);

        $catalog = BikeCatalog::resolve($data['make'], $data['model_slug'], (int) $data['year']);
        if (!$catalog) {
            return back()->withErrors(['year' => 'No catalog entry for that make/model/year.'])->withInput();
        }

        $userBike = UserBike::firstOrCreate(
            [
                'user_id' => auth()->id(),
                'bike_catalog_id' => $catalog->id,
            ],
            [
                'nickname' => $data['nickname'] ?? null,
            ]
        );

        $message = "Added {$catalog->displayLabel()} to your bikes.";

        // Auto-crawl the new bike so listings appear within minutes (only fires when the bike is freshly added).
        if ($userBike->wasRecentlyCreated) {
            $run = SyncRun::create([
                'kind' => SyncRun::KIND_CRAWL_BIKE,
                'status' => SyncRun::STATUS_QUEUED,
                'triggered_by' => auth()->id(),
                'payload' => ['catalog_key' => $catalog->catalog_key],
            ]);
            CrawlBikeJob::dispatch($run->id, $catalog->catalog_key)->onQueue('sync');
            $message .= ' Crawl queued — listings will appear within a couple of minutes.';
        }

        return redirect()
            ->route('my-bikes.index')
            ->with('status', $message);
    }

    public function destroy(UserBike $bike)
    {
        abort_unless($bike->user_id === auth()->id(), 403);
        $bike->delete();
        return redirect()->route('my-bikes.index')->with('status', 'Bike removed.');
    }
}
