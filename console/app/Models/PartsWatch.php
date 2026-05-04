<?php

namespace App\Models;

use App\Models\Watcher\BikeCatalog;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PartsWatch extends Model
{
    protected $table = 'parts_watches';

    protected $fillable = [
        'user_id', 'bike_catalog_id', 'query',
        'is_high_priority', 'priority_revoked_at',
        'last_crawled_at', 'match_count',
    ];

    protected $casts = [
        'is_high_priority' => 'boolean',
        'priority_revoked_at' => 'datetime',
        'last_crawled_at' => 'datetime',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function bikeCatalog(): ?BikeCatalog
    {
        return $this->bike_catalog_id ? BikeCatalog::find($this->bike_catalog_id) : null;
    }
}
