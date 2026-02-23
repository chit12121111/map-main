<?php

use App\Http\Controllers\CheckinController;
use App\Http\Controllers\PlaceController;
use App\Http\Controllers\EmailController;
use App\Http\Controllers\DiscoveredUrlController;
use App\Http\Controllers\StatsController;
use App\Http\Controllers\PipelineController;
use App\Http\Controllers\EmailCampaignController;
use Illuminate\Support\Facades\Route;

// Check-in API (same paths as FastAPI)
Route::post('/create-token', [CheckinController::class, 'createToken']);
Route::get('/tokens', [CheckinController::class, 'getTokens']);
Route::get('/checkins', [CheckinController::class, 'getCheckins']);
Route::post('/response', [CheckinController::class, 'recordResponse']);
Route::get('/responses', [CheckinController::class, 'getResponses']);

// Pipeline API
Route::get('/stats', [StatsController::class, 'index']);
Route::post('/places/import', [PlaceController::class, 'import']);
Route::post('/places/clear', [PlaceController::class, 'clear']);
Route::apiResource('places', PlaceController::class)->only(['index', 'store', 'show', 'update', 'destroy']);
Route::post('/emails/bulk-delete', [EmailController::class, 'bulkDelete']);
Route::apiResource('emails', EmailController::class)->only(['index', 'store', 'show', 'update', 'destroy']);
Route::post('/email-campaigns/preview', [EmailCampaignController::class, 'preview']);
Route::post('/email-campaigns/send', [EmailCampaignController::class, 'send']);
Route::get('/email-campaigns', [EmailCampaignController::class, 'index']);
Route::get('/email-campaigns/{id}', [EmailCampaignController::class, 'show']);
Route::apiResource('discovered-urls', DiscoveredUrlController::class)->only(['index', 'store', 'show', 'update', 'destroy']);
Route::post('/pipeline/run', [PipelineController::class, 'run']);
Route::get('/pipeline/status', [PipelineController::class, 'status']);
Route::get('/pipeline/runs', [PipelineController::class, 'runs']);
Route::get('/pipeline/runs/{id}', [PipelineController::class, 'runDetail']);
Route::get('/pipeline/runs/{id}/logs', [PipelineController::class, 'runLogs']);
Route::get('/ui-preferences/{key}', [PipelineController::class, 'getPreference']);
Route::put('/ui-preferences/{key}', [PipelineController::class, 'putPreference']);
