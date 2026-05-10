<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

class PartsGlossary extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'parts_glossary';

    protected $fillable = [
        'slug', 'term_en', 'term_zh', 'term_ja',
        'category', 'notes', 'source', 'contributed_by_user_id',
    ];

    public function scopeSearch(Builder $query, string $term): Builder
    {
        $like = '%' . addcslashes($term, '%_') . '%';
        return $query->where(fn (Builder $sub) => $sub
            ->whereRaw('term_en ILIKE ?', [$like])
            ->orWhereRaw('term_zh ILIKE ?', [$like])
            ->orWhereRaw('term_ja ILIKE ?', [$like])
        );
    }
}
