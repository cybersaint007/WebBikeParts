<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncRun extends Model
{
    protected $table = 'sync_runs';

    protected $fillable = [
        'kind', 'status', 'triggered_by', 'payload',
        'started_at', 'finished_at', 'output_excerpt',
    ];

    protected $casts = [
        'payload' => 'array',
        'started_at' => 'datetime',
        'finished_at' => 'datetime',
    ];

    public const KIND_CATALOG = 'catalog';
    public const KIND_CRAWL_BIKE = 'crawl_bike';
    public const KIND_LIVE_SEARCH = 'live_search';
    public const KIND_CRAWL_ALL = 'crawl_all';
    public const KIND_CRAWL_WATCHES = 'crawl_watches';
    public const KIND_CLEANSE_LISTINGS = 'cleanse_listings';

    public const STATUS_QUEUED = 'queued';
    public const STATUS_RUNNING = 'running';
    public const STATUS_SUCCESS = 'success';
    public const STATUS_FAILED = 'failed';

    public function triggeredBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'triggered_by');
    }

    public function isInFlight(): bool
    {
        return in_array($this->status, [self::STATUS_QUEUED, self::STATUS_RUNNING], true);
    }

    public function markRunning(): void
    {
        $this->update(['status' => self::STATUS_RUNNING, 'started_at' => now()]);
    }

    public function markSuccess(?string $output = null): void
    {
        $this->update([
            'status' => self::STATUS_SUCCESS,
            'finished_at' => now(),
            'output_excerpt' => $output ? substr($output, -4000) : $this->output_excerpt,
        ]);
    }

    public function markFailed(?string $output = null): void
    {
        $this->update([
            'status' => self::STATUS_FAILED,
            'finished_at' => now(),
            'output_excerpt' => $output ? substr($output, -4000) : $this->output_excerpt,
        ]);
    }
}
