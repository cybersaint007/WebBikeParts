<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class EbayController extends Controller
{
    public function handleAccountDeletion(Request $request)
    {
        // Endpoint verification: eBay sends a challenge_code to confirm ownership
        if ($request->has('challenge_code')) {
            $hash = hash('sha256',
                $request->challenge_code
                . config('services.ebay.verification_token')
                . url('/ebay/account-deletion')
            );
            return response()->json(['challengeResponse' => $hash]);
        }

        // Validate eBay signature header is present
        if (! $request->hasHeader('X-EBAY-SIGNATURE')) {
            return response()->json(['error' => 'Missing signature'], 401);
        }

        // Extract the seller username from either possible payload shape
        $username = $request->input('metadata.username')
                 ?? $request->input('data.username');

        if ($username) {
            $deleted = DB::connection('pgsql_watcher')
                ->table('listings')
                ->where('seller_name', $username)
                ->delete();

            Log::info("eBay account deletion: removed {$deleted} listing(s) for seller '{$username}'");
        }

        return response()->json(['status' => 'ok']);
    }
}
