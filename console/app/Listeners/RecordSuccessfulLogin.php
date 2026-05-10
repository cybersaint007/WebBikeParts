<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Login;

class RecordSuccessfulLogin
{
    public function handle(Login $event): void
    {
        $record = LoginHistory::record($event->user->getKey(), null, true);
        session(['login_history_id' => $record->id]);
    }
}
