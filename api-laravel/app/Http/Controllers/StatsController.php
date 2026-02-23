<?php

namespace App\Http\Controllers;

use App\Models\DiscoveredUrl;
use App\Models\Email;
use App\Models\Place;
use Illuminate\Http\JsonResponse;

class StatsController extends Controller
{
    public function index(): JsonResponse
    {
        $totalPlaces = Place::count();
        $statusBreakdown = Place::query()
            ->selectRaw('status, count(*) as count')
            ->groupBy('status')
            ->pluck('count', 'status')
            ->all();

        $totalEmails = Email::count();
        $sourceBreakdown = Email::query()
            ->selectRaw('source, count(*) as count')
            ->groupBy('source')
            ->pluck('count', 'source')
            ->all();

        $totalDiscovered = DiscoveredUrl::count();
        $discoveredBreakdown = DiscoveredUrl::query()
            ->selectRaw('status, count(*) as count')
            ->groupBy('status')
            ->pluck('count', 'status')
            ->all();
        $discoveredTypes = DiscoveredUrl::query()
            ->selectRaw('url_type, count(*) as count')
            ->groupBy('url_type')
            ->pluck('count', 'url_type')
            ->all();

        $placesWithEmail = (int) \DB::table('emails')->selectRaw('COUNT(DISTINCT place_id) as c')->value('c');

        return response()->json([
            'total_places' => $totalPlaces,
            'places_with_email' => $placesWithEmail,
            'status_breakdown' => $statusBreakdown,
            'total_emails' => $totalEmails,
            'source_breakdown' => $sourceBreakdown,
            'total_discovered' => $totalDiscovered,
            'discovered_breakdown' => $discoveredBreakdown,
            'discovered_types' => $discoveredTypes,
        ]);
    }
}
