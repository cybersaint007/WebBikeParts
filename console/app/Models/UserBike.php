<?php

namespace App\Models;

use App\Models\Watcher\BikeCatalog;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class UserBike extends Model
{
    protected $table = 'user_bikes';
    public $timestamps = false;

    protected $fillable = ['user_id', 'bike_catalog_id', 'nickname'];

    protected $casts = [
        'created_at' => 'datetime',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Cross-connection lookup (BikeCatalog lives on pgsql_watcher).
     */
    public function bikeCatalog(): ?BikeCatalog
    {
        return BikeCatalog::find($this->bike_catalog_id);
    }
}
