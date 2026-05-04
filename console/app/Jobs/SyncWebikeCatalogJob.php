<?php

namespace App\Jobs;

class SyncWebikeCatalogJob extends RunPartsWatchJob
{
    protected function arguments(): array
    {
        return ['sync-catalog'];
    }
}
