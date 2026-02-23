<?php

use App\Http\Controllers\CheckinController;
use Illuminate\Support\Facades\Route;

Route::get('/health', function () {
    return response()->json([
        'status' => 'ok',
        'message' => 'API is running',
        'timestamp' => now()->utc()->toIso8601String(),
    ]);
});

Route::post('/checkin', [CheckinController::class, 'checkin']);

Route::get('/', function () {
    return view('checkin-info');
});
Route::get('/index.html', [CheckinController::class, 'checkinPage']);
Route::get('/checkin', [CheckinController::class, 'checkinPage']);
