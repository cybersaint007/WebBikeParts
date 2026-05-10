<?php

use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Auth;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PartsController;
use App\Http\Controllers\MyBikesController;
use App\Http\Controllers\CatalogLookupController;
use App\Http\Controllers\SyncController;
use App\Http\Controllers\WatchListController;
use App\Http\Controllers\Admin\UsersController as AdminUsersController;
use App\Http\Controllers\Admin\AdapterStatusController;
use App\Http\Controllers\ProfileController;

Auth::routes(['register' => false]);

Route::match(['GET', 'POST'], '/ebay/account-deletion', [App\Http\Controllers\EbayController::class, 'handleAccountDeletion']);

Route::get('index/{locale}', [App\Http\Controllers\HomeController::class, 'lang']);

Route::get('/', [DashboardController::class, 'index'])->name('root');

Route::middleware('auth')->group(function () {
    Route::get('/parts', [PartsController::class, 'index'])->name('parts.index');
    Route::get('/parts/search.json', [PartsController::class, 'searchJson'])->name('parts.search');
    Route::post('/parts/live-search', [PartsController::class, 'liveSearch'])->name('parts.live-search');
    Route::get('/parts/{listing}', [PartsController::class, 'show'])->name('parts.show');

    Route::get('/my-bikes', [MyBikesController::class, 'index'])->name('my-bikes.index');
    Route::post('/my-bikes', [MyBikesController::class, 'store'])->name('my-bikes.store');
    Route::delete('/my-bikes/{bike}', [MyBikesController::class, 'destroy'])->name('my-bikes.destroy');
    Route::post('/my-bikes/{catalogKey}/refresh-image', [MyBikesController::class, 'refreshImage'])->name('my-bikes.refresh-image');
    Route::post('/my-bikes/{catalogKey}/upload-image',  [MyBikesController::class, 'uploadImage'])->name('my-bikes.upload-image');

    Route::get('/api/catalog/makes',  [CatalogLookupController::class, 'makes']);
    Route::get('/api/catalog/models', [CatalogLookupController::class, 'models']);
    Route::get('/api/catalog/years',  [CatalogLookupController::class, 'years']);

    Route::post('/sync',           [SyncController::class, 'store'])->name('sync.store');
    Route::get('/sync/{run}.json', [SyncController::class, 'show'])->name('sync.show');

    Route::get('/profile',           [ProfileController::class, 'show'])->name('profile.show');
    Route::patch('/profile',         [ProfileController::class, 'update'])->name('profile.update');
    Route::patch('/profile/password',[ProfileController::class, 'updatePassword'])->name('profile.password');

    Route::get('/watch-list',                    [WatchListController::class, 'index'])->name('watch-list.index');
    Route::patch('/watch-list/{watch}/priority', [WatchListController::class, 'togglePriority'])->name('watch-list.priority');
    Route::delete('/watch-list/{watch}',         [WatchListController::class, 'destroy'])->name('watch-list.destroy');

    Route::middleware('admin')->prefix('admin')->name('admin.')->group(function () {
        Route::resource('users', AdminUsersController::class)->names('users');
        Route::get('users/{user}/login-history', [AdminUsersController::class, 'loginHistory'])->name('users.login-history');
        Route::get('adapters', [AdapterStatusController::class, 'index'])->name('adapters.index');
        Route::get('adapters/status.json', [AdapterStatusController::class, 'status'])->name('adapters.status');
    });
});

Route::get('{any}', [App\Http\Controllers\HomeController::class, 'index'])->name('index');
