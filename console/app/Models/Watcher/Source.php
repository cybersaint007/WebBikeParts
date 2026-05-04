<?php

namespace App\Models\Watcher;

use Illuminate\Database\Eloquent\Model;

class Source extends Model
{
    protected $connection = 'pgsql_watcher';
    protected $table = 'sources';
    public $timestamps = false;

    protected $casts = [
        'enabled' => 'boolean',
    ];
}
