<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Failed;

class RecordFailedLogin
{
    public function handle(Failed $event): void
    {
        LoginHistory::create([
            'user_id'    => $event->user?->getKey(),
            'email'      => $event->credentials['email'] ?? null,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'success'    => false,
            'login_at'   => now(),
        ]);
    }
}
