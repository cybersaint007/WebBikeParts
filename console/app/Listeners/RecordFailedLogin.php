<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Failed;

class RecordFailedLogin
{
    public function handle(Failed $event): void
    {
        LoginHistory::record(
            $event->user?->getKey(),
            $event->credentials['email'] ?? null,
            false,
        );
    }
}
