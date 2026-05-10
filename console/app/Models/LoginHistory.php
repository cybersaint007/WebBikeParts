<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class LoginHistory extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'user_id',
        'email',
        'ip_address',
        'user_agent',
        'success',
        'login_at',
        'logout_at',
    ];

    protected $casts = [
        'success'   => 'boolean',
        'login_at'  => 'datetime',
        'logout_at' => 'datetime',
    ];

    public static function record(?int $userId, ?string $email, bool $success): static
    {
        return static::create([
            'user_id'    => $userId,
            'email'      => $email,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'success'    => $success,
            'login_at'   => now(),
        ]);
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    protected function duration(): Attribute
    {
        return Attribute::get(function () {
            if (!$this->logout_at) {
                return null;
            }
            $seconds = $this->login_at->diffInSeconds($this->logout_at);
            if ($seconds < 60) {
                return "{$seconds}s";
            }
            $minutes = (int) ($seconds / 60);
            if ($minutes < 60) {
                return "{$minutes}m";
            }
            $hours = (int) ($minutes / 60);
            $rem   = $minutes % 60;
            return $rem > 0 ? "{$hours}h {$rem}m" : "{$hours}h";
        });
    }
}
