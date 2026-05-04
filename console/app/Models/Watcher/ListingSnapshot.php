<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ListingSnapshot extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'listing_snapshots';
    public $timestamps = false;

    protected $casts = [
        'price_amount' => 'decimal:2',
        'checked_at' => 'datetime',
        'raw_json' => 'array',
    ];

    public function listing(): BelongsTo
    {
        return $this->belongsTo(Listing::class, 'listing_id');
    }
}
