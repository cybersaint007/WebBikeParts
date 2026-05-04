<?php

namespace App\Http\Controllers;

use App\Models\PartsWatch;
use App\Models\Watcher\BikeCatalog;

class WatchListController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function index()
    {
        $watches = auth()->user()->partsWatches()
            ->orderByDesc('is_high_priority')
            ->orderByDesc('updated_at')
            ->get();

        $catalogIds = $watches->pluck('bike_catalog_id')->filter()->unique()->all();
        $catalogs = BikeCatalog::query()->whereIn('id', $catalogIds)->get()->keyBy('id');

        return view('watch-list.index', compact('watches', 'catalogs'));
    }

    public function togglePriority(PartsWatch $watch)
    {
        abort_unless($watch->user_id === auth()->id(), 403);
        if ($watch->is_high_priority) {
            $watch->is_high_priority = false;
            $watch->priority_revoked_at = now();
        } else {
            $watch->is_high_priority = true;
            $watch->priority_revoked_at = null;
        }
        $watch->save();
        return back()->with('status', $watch->is_high_priority ? 'Promoted to high priority.' : 'Priority revoked.');
    }

    public function destroy(PartsWatch $watch)
    {
        abort_unless($watch->user_id === auth()->id(), 403);
        $watch->delete();
        return back()->with('status', 'Watch removed.');
    }
}
