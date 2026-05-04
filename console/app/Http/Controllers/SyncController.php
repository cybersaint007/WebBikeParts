<?php

namespace App\Http\Controllers;

use App\Jobs\SyncWebikeCatalogJob;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

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
        return response()->json([
            'id' => $run->id,
            'kind' => $run->kind,
            'status' => $run->status,
            'started_at' => $run->started_at?->toIso8601String(),
            'finished_at' => $run->finished_at?->toIso8601String(),
            'output_excerpt' => $run->output_excerpt,
        ]);
    }
}
