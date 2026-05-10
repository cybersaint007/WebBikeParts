<?php

namespace App\Http\Controllers;

use App\Jobs\SyncWebikeCatalogJob;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class SyncController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'kind' => ['required', 'in:catalog'],
        ]);

        // Block when an in-flight run already exists for this kind.
        $inflight = SyncRun::query()
            ->where('kind', $data['kind'])
            ->whereIn('status', [SyncRun::STATUS_QUEUED, SyncRun::STATUS_RUNNING])
            ->first();

        if ($inflight) {
            return back()->with('status', 'A sync is already running. Wait for it to finish.');
        }

        $run = SyncRun::create([
            'kind' => $data['kind'],
            'status' => SyncRun::STATUS_QUEUED,
            'triggered_by' => $request->user()->id,
        ]);

        SyncWebikeCatalogJob::dispatch($run->id)->onQueue('sync');

        return back()->with('status', 'Sync queued — refresh the page in a few minutes.');
    }

    public function show(SyncRun $run): JsonResponse
    {
        $payload = [
            'id' => $run->id,
            'kind' => $run->kind,
            'status' => $run->status,
            'started_at' => $run->started_at?->toIso8601String(),
            'finished_at' => $run->finished_at?->toIso8601String(),
            'output_excerpt' => $run->output_excerpt,
        ];

        // While a live search is running, count crawl_jobs so the UI can show a progress bar.
        // The Python subprocess enqueues all jobs within ~30 s of the SyncRun being created.
        if ($run->status === SyncRun::STATUS_RUNNING && $run->kind === SyncRun::KIND_LIVE_SEARCH) {
            $batch = DB::connection('pgsql_watcher')
                ->table('crawl_jobs')
                ->where('enqueued_by', 'like', 'live-search:%')
                ->whereBetween('created_at', [
                    $run->created_at->subSeconds(5),
                    $run->created_at->addSeconds(90),
                ])
                ->selectRaw("COUNT(*) as total, COUNT(*) FILTER (WHERE status IN ('completed','failed')) as done")
                ->first();

            if ($batch && $batch->total > 0) {
                $payload['jobs_done']  = (int) $batch->done;
                $payload['jobs_total'] = (int) $batch->total;
            }
        }

        return response()->json($payload);
    }
}
