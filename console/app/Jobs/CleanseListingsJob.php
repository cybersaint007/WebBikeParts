<?php

namespace App\Jobs;

class CleanseListingsJob extends RunPartsWatchJob
{
    protected function arguments(): array
    {
        return ['cleanse-listings', '--older-than-days', '14'];
    }
}
