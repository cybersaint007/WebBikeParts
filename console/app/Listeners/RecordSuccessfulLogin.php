<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Login;

class RecordSuccessfulLogin
{
    public function handle(Login $event): void
    {
        LoginHistory::create([
            'user_id'    => $event->user->getKey(),
            'email'      => $event->user->email,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'success'    => true,
            'login_at'   => now(),
        ]);
    }
}
