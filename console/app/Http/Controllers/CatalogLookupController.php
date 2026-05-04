<?php

namespace App\Http\Controllers;

use App\Models\Watcher\BikeCatalog;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CatalogLookupController extends Controller
{
    public function __construct()
    {
        $this->middleware('auth');
    }

    public function makes(): JsonResponse
    {
        return response()->json(BikeCatalog::availableMakes()->values());
    }

    public function models(Request $request): JsonResponse
    {
        $request->validate(['make' => ['required', 'string']]);
        return response()->json(BikeCatalog::modelsForMake($request->string('make'))->values());
    }

    public function years(Request $request): JsonResponse
    {
        $request->validate([
            'make' => ['required', 'string'],
            'model_slug' => ['required', 'string'],
        ]);
        return response()->json(BikeCatalog::yearsForModel(
            $request->string('make'),
            $request->string('model_slug')
        ));
    }
}
