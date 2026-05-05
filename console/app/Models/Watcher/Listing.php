<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Listing extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'listings';
    public $timestamps = false;

    protected $casts = [
        'price_amount' => 'decimal:2',
        'shipping_amount' => 'decimal:2',
        'first_seen_at' => 'datetime',
        'last_seen_at' => 'datetime',
        'raw_json' => 'array',
    ];

    public function snapshots(): HasMany
    {
        return $this->hasMany(ListingSnapshot::class, 'listing_id');
    }

    public function scopeForBikeKeys(Builder $q, array $keys): Builder
    {
        return empty($keys) ? $q->whereRaw('1=0') : $q->whereIn('bike_key', $keys);
    }

    public function scopeCategory(Builder $q, ?string $category): Builder
    {
        return $category ? $q->where('category', $category) : $q;
    }

    public function scopeSubcategory(Builder $q, ?string $subcategory): Builder
    {
        return $subcategory ? $q->where('subcategory', $subcategory) : $q;
    }

    public function scopeSource(Builder $q, ?string $source): Builder
    {
        return $source ? $q->where('source_name', $source) : $q;
    }

    public function scopeCondition(Builder $q, ?string $condition): Builder
    {
        return $condition ? $q->where('condition', $condition) : $q;
    }

    public function scopePriceBetween(Builder $q, ?float $min, ?float $max): Builder
    {
        if ($min !== null) $q->where('price_amount', '>=', $min);
        if ($max !== null) $q->where('price_amount', '<=', $max);
        return $q;
    }

    public function scopeSearch(Builder $q, ?string $term): Builder
    {
        $term = trim((string) $term);
        if ($term === '') return $q;
        $like = '%' . str_replace(['%', '_'], ['\%', '\_'], $term) . '%';
        return $q->where(function (Builder $w) use ($like) {
            $w->where('title', 'ILIKE', $like)
              ->orWhere('description', 'ILIKE', $like)
              ->orWhere('part_number', 'ILIKE', $like)
              ->orWhere('fitment_text', 'ILIKE', $like);
        });
    }
}
