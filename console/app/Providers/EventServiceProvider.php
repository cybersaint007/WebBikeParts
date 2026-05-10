<?php

namespace App\Providers;

use App\Listeners\RecordFailedLogin;
use App\Listeners\RecordLogout;
use App\Listeners\RecordSuccessfulLogin;
use Illuminate\Auth\Events\Failed;
use Illuminate\Auth\Events\Login;
use Illuminate\Auth\Events\Logout;
use Illuminate\Auth\Events\Registered;
use Illuminate\Auth\Listeners\SendEmailVerificationNotification;
use Illuminate\Foundation\Support\Providers\EventServiceProvider as ServiceProvider;

class EventServiceProvider extends ServiceProvider
{
    protected $listen = [
        Registered::class => [
            SendEmailVerificationNotification::class,
        ],
        Login::class => [
            RecordSuccessfulLogin::class,
        ],
        Failed::class => [
            RecordFailedLogin::class,
        ],
        Logout::class => [
            RecordLogout::class,
        ],
    ];

    public function boot()
    {
        //
    }
}
