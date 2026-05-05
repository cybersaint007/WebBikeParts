<?php

namespace App\Http\Middleware;

use App\Services\IpLocaleResolver;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\App;
use Illuminate\Support\Facades\Cookie;
use Illuminate\Support\Facades\Session;

class Localization
{
    public function __construct(private readonly IpLocaleResolver $resolver)
    {
    }

    /**
     * Resolution order: explicit ?lang= → session → cookie → IP geolocation → fallback.
     * The first valid hit is persisted to the session for subsequent requests.
     */
    public function handle(Request $request, Closure $next)
    {
        $available = config('app.available_locales', ['en']);
        $fallback  = config('app.fallback_locale', 'en');

        $locale = $this->normalize($request->query('lang'), $available)
            ?? $this->normalize(Session::get('lang'), $available)
            ?? $this->normalize($request->cookie('lang'), $available)
            ?? $this->normalize($this->resolver->resolve($request->ip()), $available)
            ?? $fallback;

        App::setLocale($locale);
        Session::put('lang', $locale);
        Cookie::queue('lang', $locale, 60 * 24 * 365);

        return $next($request);
    }

    private function normalize(?string $candidate, array $available): ?string
    {
        if (!$candidate) {
            return null;
        }
        $candidate = trim($candidate);
        if (in_array($candidate, $available, true)) {
            return $candidate;
        }
        // Allow case-insensitive match for `zh-tw` vs `zh-TW`.
        foreach ($available as $supported) {
            if (strcasecmp($supported, $candidate) === 0) {
                return $supported;
            }
        }
        return null;
    }
}
