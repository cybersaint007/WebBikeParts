<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Model;

class CrawlJob extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'crawl_jobs';
    public $timestamps = false;

    protected $casts = [
        'locked_at'    => 'datetime',
        'started_at'   => 'datetime',
        'completed_at' => 'datetime',
        'created_at'   => 'datetime',
    ];

    public const STATUSES = ['pending', 'running', 'completed', 'failed'];
}
