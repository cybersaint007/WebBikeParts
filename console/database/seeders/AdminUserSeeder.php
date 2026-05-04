<?php

namespace Database\Seeders;

use App\Models\User;
use App\Models\UserBike;
use App\Models\Watcher\BikeCatalog;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class AdminUserSeeder extends Seeder
{
    public function run(): void
    {
        $email = env('ADMIN_EMAIL', 'admin@example.com');
        $password = env('ADMIN_PASSWORD', 'changeme123');

        $admin = User::firstOrCreate(
            ['email' => $email],
            [
                'name' => 'Admin',
                'password' => Hash::make($password),
                'email_verified_at' => now(),
                'role' => User::ROLE_ADMIN,
            ]
        );

        if ($admin->role !== User::ROLE_ADMIN) {
            $admin->role = User::ROLE_ADMIN;
            $admin->save();
        }

        // Seed default My Bike entries from the legacy bootstrap catalog rows, if present.
        foreach (['suzuki-katana-1100-1990', 'suzuki-gsx1300r-2003'] as $key) {
            $catalog = BikeCatalog::where('catalog_key', $key)->first();
            if (!$catalog) continue;

            UserBike::firstOrCreate(
                ['user_id' => $admin->id, 'bike_catalog_id' => $catalog->id]
            );
        }
    }
}
