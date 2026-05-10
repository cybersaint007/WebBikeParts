<?php

namespace App\Http\Controllers;

use App\Models\Watcher\PartsGlossary;
use App\Services\TranslationService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\View\View;

class GlossaryController extends Controller
{
    private const CATEGORIES = [
        'engine', 'brakes', 'electrical', 'suspension', 'drivetrain',
        'exhaust', 'fuel', 'cooling', 'frame', 'body', 'wheels',
        'fasteners', 'general',
    ];

    public function index(): View
    {
        $columns = self::columnsForLocale(app()->getLocale());
        $primary = $columns[0]['field'];

        $grouped = PartsGlossary::get()
            ->sortBy(fn ($e) => mb_strtolower((string) ($e->{$primary} ?: $e->term_en)))
            ->groupBy('category')
            ->sortKeys();

        $modalFields = [
            'en' => ['label' => __('English'), 'name' => 'term_en', 'placeholder' => 'e.g. fork bushing'],
            'zh' => ['label' => '繁體中文',     'name' => 'term_zh', 'placeholder' => 'e.g. 前叉襯套'],
            'ja' => ['label' => '日本語',       'name' => 'term_ja', 'placeholder' => 'e.g. フォークブッシュ'],
        ];

        return view('glossary.index', [
            'grouped'       => $grouped,
            'categories'    => self::CATEGORIES,
            'columns'       => $columns,
            'modalFields'   => $modalFields,
            'columnFields'  => array_column($columns, 'field'),
        ]);
    }

    /**
     * Three language columns ordered to put the current locale first.
     * Each column: ['code' => 'en|zh|ja', 'field' => 'term_*', 'label' => header text].
     *
     * @return array<int, array{code: string, field: string, label: string}>
     */
    public static function columnsForLocale(string $locale): array
    {
        $en = ['code' => 'en', 'field' => 'term_en', 'label' => 'English'];
        $zh = ['code' => 'zh', 'field' => 'term_zh', 'label' => '繁中'];
        $ja = ['code' => 'ja', 'field' => 'term_ja', 'label' => '日本語'];

        return match ($locale) {
            'zh-TW' => [$zh, $en, $ja],
            'ja'    => [$ja, $en, $zh],
            default => [$en, $zh, $ja],
        };
    }

    public function searchJson(Request $request): JsonResponse
    {
        $q = $request->string('q')->trim()->toString();
        if (strlen($q) < 1) {
            return response()->json([]);
        }

        $primary = self::columnsForLocale(app()->getLocale())[0]['field'];

        $results = PartsGlossary::search($q)
            ->orderByRaw("LOWER(COALESCE(NULLIF({$primary}, ''), term_en))")
            ->limit(50)
            ->get(['id', 'slug', 'term_en', 'term_zh', 'term_ja', 'category', 'source']);

        return response()->json($results);
    }

    public function autocomplete(Request $request): JsonResponse
    {
        $q = $request->string('q')->trim()->toString();
        if (strlen($q) < 2) {
            return response()->json([]);
        }

        $results = PartsGlossary::search($q)
            ->orderByRaw("CASE WHEN LOWER(term_en) = LOWER(?) THEN 0 ELSE 1 END, term_en", [$q])
            ->limit(10)
            ->get(['slug', 'term_en', 'term_zh', 'term_ja']);

        return response()->json($results->map(fn ($r) => [
            'slug' => $r->slug,
            'en'   => $r->term_en,
            'zh'   => $r->term_zh,
            'ja'   => $r->term_ja,
        ]));
    }

    public function store(Request $request, TranslationService $translator): RedirectResponse
    {
        $data = $request->validate([
            'term_en'  => ['nullable', 'string', 'max:200'],
            'term_zh'  => ['nullable', 'string', 'max:200'],
            'term_ja'  => ['nullable', 'string', 'max:200'],
            'category' => ['required', 'string', 'in:' . implode(',', self::CATEGORIES)],
            'notes'    => ['nullable', 'string', 'max:500'],
        ]);

        $termEn = trim($data['term_en'] ?? '');
        $termZh = trim($data['term_zh'] ?? '');
        $termJa = trim($data['term_ja'] ?? '');

        if ($termEn === '' && $termZh === '' && $termJa === '') {
            return back()->withErrors(['term_en' => __('At least one language field is required')])->withInput();
        }

        // Require at least two fields if no API key is configured
        $filledCount = (int)($termEn !== '') + (int)($termZh !== '') + (int)($termJa !== '');
        if (!$translator->isAvailable() && $filledCount < 2) {
            return back()->withErrors(['term_en' => __('At least two language fields are required when auto-translation is not configured')])->withInput();
        }

        $terms = $translator->fillMissing([
            'en' => $termEn ?: null,
            'zh' => $termZh ?: null,
            'ja' => $termJa ?: null,
        ]);

        // slug must be derived from an EN term
        $slugBase = $terms['en'] ?? ($termZh ?: $termJa);
        $slug = Str::slug($slugBase);
        if (empty($slug)) {
            return back()->withErrors(['term_en' => __('Could not generate a URL slug from the provided term')])->withInput();
        }

        // Make slug unique if it conflicts
        $base = $slug;
        $i    = 2;
        while (PartsGlossary::where('slug', $slug)->exists()) {
            $slug = "{$base}-{$i}";
            $i++;
        }

        $entry = new PartsGlossary();
        $entry->slug                   = $slug;
        $entry->term_en                = $terms['en'];
        $entry->term_zh                = $terms['zh'];
        $entry->term_ja                = $terms['ja'];
        $entry->category               = $data['category'];
        $entry->notes                  = $data['notes'] ?? null;
        $entry->source                 = 'user';
        $entry->contributed_by_user_id = auth()->id();
        $entry->save();

        $translationNote = ($filledCount < 3 && $translator->isAvailable())
            ? __('Translation auto-filled by AI')
            : null;

        return redirect()->route('glossary.index')
            ->with('success', __('Term saved successfully') . ($translationNote ? " ({$translationNote})" : ''));
    }
}
