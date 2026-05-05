<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class IpLocaleResolver
{
    /**
     * Country code (ISO 3166-1 alpha-2) → application locale.
     * Anything not listed falls through to the configured fallback.
     */
    private const COUNTRY_TO_LOCALE = [
        'JP' => 'ja',
        'TW' => 'zh-TW',
        'HK' => 'zh-TW',
        'MO' => 'zh-TW',
    ];

    public function resolve(?string $ip): ?string
    {
        if (!$ip || !filter_var($ip, FILTER_VALIDATE_IP)) {
            return null;
        }
        // Private / loopback / reserved IPs can't be geo-located.
        if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
            return null;
        }

        $country = Cache::remember(
            "geoip:country:{$ip}",
            now()->addDay(),
            fn () => $this->lookupCountry($ip),
        );

        if (!$country) {
            return null;
        }

        return self::COUNTRY_TO_LOCALE[$country] ?? null;
    }

    private function lookupCountry(string $ip): ?string
    {
        try {
            $response = Http::timeout(1.5)
                ->retry(1, 100)
                ->get("http://ip-api.com/json/{$ip}", ['fields' => 'status,countryCode']);

            if (!$response->successful()) {
                return null;
            }
            $data = $response->json();
            if (($data['status'] ?? null) !== 'success') {
                return null;
            }
            return $data['countryCode'] ?? null;
        } catch (\Throwable $e) {
            Log::debug('ip-api lookup failed', ['ip' => $ip, 'error' => $e->getMessage()]);
            return null;
        }
    }
}
