<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Logout;

class RecordLogout
{
    public function handle(Logout $event): void
    {
        LoginHistory::query()
            ->where('user_id', $event->user->getKey())
            ->where('success', true)
            ->whereNull('logout_at')
            ->latest('login_at')
            ->limit(1)
            ->update(['logout_at' => now()]);
    }
}
