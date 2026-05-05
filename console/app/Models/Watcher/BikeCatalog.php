<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Collection;

class BikeCatalog extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'bike_catalog';
    public $timestamps = true;

    protected $fillable = [
        'make', 'model', 'model_slug', 'year_start', 'year_end',
        'displacement_cc', 'webike_url', 'catalog_key',
    ];

    public static function availableMakes(): Collection
    {
        return static::query()
            ->select('make')
            ->distinct()
            ->orderBy('make')
            ->pluck('make');
    }

    public static function modelsForMake(string $make): Collection
    {
        return static::query()
            ->select('model_slug', 'model')
            ->where('make', $make)
            ->groupBy('model_slug', 'model')
            ->orderBy('model')
            ->get();
    }

    public static function yearsForModel(string $make, string $modelSlug): array
    {
        $rows = static::query()
            ->select('year_start', 'year_end')
            ->where('make', $make)
            ->where('model_slug', $modelSlug)
            ->orderBy('year_start')
            ->get();

        $years = [];
        $hasUmbrella = false;
        foreach ($rows as $row) {
            // year_start = 0 → catalog row has no year info ("any year"). Held aside
            // until we know whether real year-range variants exist for this model.
            if ((int) $row->year_start === 0 && (int) $row->year_end === 0) {
                $hasUmbrella = true;
                continue;
            }
            for ($y = $row->year_start; $y <= $row->year_end; $y++) {
                $years[$y] = true;
            }
        }
        if (empty($years) && $hasUmbrella) {
            $years[0] = true;
        }
        ksort($years);
        return array_keys($years);
    }

    public static function resolve(string $make, string $modelSlug, int $year): ?self
    {
        $q = static::query()->where('make', $make)->where('model_slug', $modelSlug);
        if ($year === 0) {
            return $q->where('year_start', 0)->where('year_end', 0)->first();
        }
        return $q->where('year_start', '<=', $year)->where('year_end', '>=', $year)->first();
    }

    public function displayLabel(): string
    {
        if ((int) $this->year_start === 0 && (int) $this->year_end === 0) {
            return "{$this->make} {$this->model}";
        }
        $years = $this->year_start === $this->year_end
            ? (string) $this->year_start
            : "{$this->year_start}–{$this->year_end}";
        return "{$years} {$this->make} {$this->model}";
    }
}
