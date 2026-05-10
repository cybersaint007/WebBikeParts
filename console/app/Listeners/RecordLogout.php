<?php

namespace App\Listeners;

use App\Models\LoginHistory;
use Illuminate\Auth\Events\Logout;

class RecordLogout
{
    public function handle(Logout $event): void
    {
        $id = session('login_history_id');
        if ($id) {
            LoginHistory::where('id', $id)->whereNull('logout_at')->update(['logout_at' => now()]);
            session()->forget('login_history_id');
        }
    }
}
