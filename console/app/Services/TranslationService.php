<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class TranslationService
{
    private ?string $apiKey;
    private string $model;

    public function __construct()
    {
        $this->apiKey = config('services.anthropic.key') ?: null;
        $this->model  = config('services.anthropic.model', 'claude-haiku-4-5');
    }

    public function isAvailable(): bool
    {
        return !empty($this->apiKey);
    }

    /**
     * Fill null language fields using Claude API.
     *
     * @param  array{en: string|null, zh: string|null, ja: string|null}  $terms
     * @return array{en: string|null, zh: string|null, ja: string|null}
     */
    public function fillMissing(array $terms): array
    {
        $missing = array_keys(array_filter($terms, fn ($v) => $v === null || $v === ''));
        if (empty($missing) || !$this->apiKey) {
            return $terms;
        }

        $provided = array_filter($terms, fn ($v) => $v !== null && $v !== '');
        $langLabels = ['en' => 'English', 'zh' => 'Traditional Chinese', 'ja' => 'Japanese'];

        $providedLines = implode("\n", array_map(
            fn ($k, $v) => "{$langLabels[$k]}: {$v}",
            array_keys($provided),
            $provided
        ));
        $targetLangs = implode(', ', array_map(fn ($k) => $langLabels[$k], $missing));

        $prompt = "You are a motorcycle parts terminology expert.\n"
            . "Given this motorcycle part name:\n"
            . "{$providedLines}\n\n"
            . "Translate it into: {$targetLangs}\n"
            . "Use Traditional Chinese (not Simplified) for zh.\n"
            . "Return ONLY valid JSON with the requested language keys, no explanation.\n"
            . 'Example: {"zh":"煞車片","ja":"ブレーキパッド"}';

        try {
            $response = Http::timeout(15)->withHeaders([
                'x-api-key'         => $this->apiKey,
                'anthropic-version' => '2023-06-01',
                'content-type'      => 'application/json',
            ])->post('https://api.anthropic.com/v1/messages', [
                'model'      => $this->model,
                'max_tokens' => 150,
                'messages'   => [['role' => 'user', 'content' => $prompt]],
            ]);

            if (!$response->successful()) {
                Log::warning('TranslationService: API error', ['status' => $response->status()]);
                return $terms;
            }

            $text = $response->json('content.0.text', '{}');
            $data = json_decode($text, true);
            if (!is_array($data)) {
                return $terms;
            }

            foreach ($missing as $lang) {
                if (!empty($data[$lang]) && mb_strlen($data[$lang]) <= 200) {
                    $terms[$lang] = trim($data[$lang]);
                }
            }
        } catch (\Throwable $e) {
            Log::warning('TranslationService: request failed', ['error' => $e->getMessage()]);
        }

        return $terms;
    }
}
