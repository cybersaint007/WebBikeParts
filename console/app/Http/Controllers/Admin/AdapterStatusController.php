<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Watcher\CrawlJob;
use App\Models\Watcher\Source;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class AdapterStatusController extends Controller
{
    private const STALE_LOCK_MINUTES = 10;

    public function index()
    {
        return view('admin.adapters.index', [
            'pollUrl'    => route('admin.adapters.status'),
            'pollPeriod' => 5000,
        ]);
    }

    public function status(): JsonResponse
    {
        $sources = Source::query()
            ->orderBy('name')
            ->get(['name', 'type', 'base_url', 'enabled'])
            ->keyBy('name');

        $counts = CrawlJob::query()
            ->select('adapter', 'status', DB::raw('count(*) as c'))
            ->groupBy('adapter', 'status')
            ->get();

        $byAdapter = [];
        foreach ($counts as $row) {
            $byAdapter[$row->adapter][$row->status] = (int) $row->c;
        }

        $aggregates = CrawlJob::query()
            ->select(
                'adapter',
                DB::raw('max(completed_at) filter (where status = \'completed\') as last_completed_at'),
                DB::raw('max(completed_at) filter (where status = \'failed\') as last_failed_at'),
                DB::raw('max(started_at) as last_started_at'),
                DB::raw('coalesce(sum(result_ingested) filter (where status = \'completed\'), 0) as total_ingested'),
                DB::raw('coalesce(sum(result_found)    filter (where status = \'completed\'), 0) as total_found')
            )
            ->groupBy('adapter')
            ->get()
            ->keyBy('adapter');

        $staleCutoff = Carbon::now()->subMinutes(self::STALE_LOCK_MINUTES);
        $stuck = CrawlJob::query()
            ->where('status', 'running')
            ->where('locked_at', '<', $staleCutoff)
            ->select('adapter', DB::raw('count(*) as c'))
            ->groupBy('adapter')
            ->pluck('c', 'adapter');

        $lastErrors = CrawlJob::query()
            ->where('status', 'failed')
            ->whereNotNull('last_error')
            ->select('adapter', 'last_error', 'completed_at')
            ->orderByDesc('completed_at')
            ->get()
            ->groupBy('adapter')
            ->map(fn ($rows) => $rows->first());

        $adapterNames = collect($sources->keys())
            ->merge($byAdapter ? array_keys($byAdapter) : [])
            ->unique()
            ->sort()
            ->values();

        $rows = [];
        foreach ($adapterNames as $name) {
            $statuses = $byAdapter[$name] ?? [];
            $agg = $aggregates->get($name);
            $err = $lastErrors->get($name);
            $src = $sources->get($name);

            $pending   = (int) ($statuses['pending']   ?? 0);
            $running   = (int) ($statuses['running']   ?? 0);
            $completed = (int) ($statuses['completed'] ?? 0);
            $failed    = (int) ($statuses['failed']    ?? 0);
            $stuckN    = (int) ($stuck[$name] ?? 0);

            $health = $this->healthFor($src, $pending, $running, $failed, $completed, $stuckN);

            $rows[] = [
                'adapter'           => $name,
                'enabled'           => $src ? (bool) $src->enabled : null,
                'type'              => $src->type ?? null,
                'base_url'          => $src->base_url ?? null,
                'health'            => $health,
                'pending'           => $pending,
                'running'           => $running,
                'completed'         => $completed,
                'failed'            => $failed,
                'stuck'             => $stuckN,
                'total_ingested'    => (int) ($agg->total_ingested ?? 0),
                'total_found'       => (int) ($agg->total_found ?? 0),
                'last_started_at'   => optional($agg?->last_started_at)->toIso8601String(),
                'last_completed_at' => optional($agg?->last_completed_at)->toIso8601String(),
                'last_failed_at'    => optional($agg?->last_failed_at)->toIso8601String(),
                'last_error'        => $err?->last_error,
                'last_error_at'     => optional($err?->completed_at)->toIso8601String(),
            ];
        }

        return response()->json([
            'fetched_at'        => now()->toIso8601String(),
            'stale_lock_minutes'=> self::STALE_LOCK_MINUTES,
            'adapters'          => $rows,
        ]);
    }

    private function healthFor(?Source $src, int $pending, int $running, int $failed, int $completed, int $stuck): string
    {
        if ($src && !$src->enabled) return 'disabled';
        if ($stuck > 0) return 'stuck';
        if ($failed > 0 && $completed === 0) return 'failing';
        if ($running > 0) return 'running';
        if ($pending > 0) return 'queued';
        if ($completed > 0) return 'idle';
        return 'unknown';
    }
}
