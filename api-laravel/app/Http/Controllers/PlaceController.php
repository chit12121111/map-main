<?php

namespace App\Http\Controllers;

use App\Models\DiscoveredUrl;
use App\Models\Email;
use App\Models\Place;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class PlaceController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $query = Place::query()->orderBy('name');
        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }
        $perPage = (int) $request->get('per_page', 100);
        $places = $query->paginate($perPage);

        return response()->json([
            'data' => $places->items(),
            'total' => $places->total(),
            'per_page' => $places->perPage(),
            'current_page' => $places->currentPage(),
        ]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'place_id' => 'required|string',
            'name' => 'required|string',
            'website' => 'nullable|string',
            'phone' => 'nullable|string',
            'google_maps_url' => 'required|string',
            'address' => 'nullable|string',
            'category' => 'nullable|string',
            'review_count' => 'nullable|integer',
            'review_rating' => 'nullable|numeric',
            'latitude' => 'nullable|numeric',
            'longitude' => 'nullable|numeric',
            'raw_data' => 'nullable|string',
            'status' => 'nullable|string',
        ]);
        $data['raw_data'] = $data['raw_data'] ?? '{}';
        $data['status'] = $data['status'] ?? 'NEW';

        $place = Place::updateOrCreate(
            ['place_id' => $data['place_id']],
            $data
        );

        return response()->json($place, 201);
    }

    public function show(string $place): JsonResponse
    {
        $model = Place::findOrFail($place);

        return response()->json($model);
    }

    public function update(Request $request, string $place): JsonResponse
    {
        $model = Place::findOrFail($place);
        $data = $request->only(['status', 'name', 'website', 'phone', 'address', 'category']);
        $model->update($data);

        return response()->json($model);
    }

    public function destroy(string $place): JsonResponse
    {
        Place::findOrFail($place)->delete();

        return response()->json(['message' => 'Deleted'], 200);
    }

    public function import(Request $request): JsonResponse
    {
        $payload = $request->input('places', $request->all());
        if (! is_array($payload)) {
            return response()->json(['error' => 'places must be an array'], 422);
        }
        $created = 0;
        $updated = 0;
        foreach ($payload as $row) {
            $placeId = $row['place_id'] ?? $row['cid'] ?? ('place_'.$created.$updated);
            $name = $row['name'] ?? $row['title'] ?? 'Unknown';
            $existing = Place::find($placeId);
            $data = [
                'place_id' => $placeId,
                'name' => $name,
                'website' => $row['website'] ?? $row['url'] ?? null,
                'phone' => $row['phone'] ?? null,
                'google_maps_url' => $row['google_maps_url'] ?? $row['url'] ?? $row['website'] ?? '',
                'address' => $row['address'] ?? null,
                'category' => $row['category'] ?? null,
                'review_count' => isset($row['review_count']) ? (int) $row['review_count'] : null,
                'review_rating' => isset($row['review_rating']) ? (float) $row['review_rating'] : null,
                'latitude' => isset($row['latitude']) ? (float) $row['latitude'] : null,
                'longitude' => isset($row['longitude']) ? (float) $row['longitude'] : null,
                'raw_data' => is_string($row['raw_data'] ?? null) ? $row['raw_data'] : json_encode($row),
                'status' => 'NEW',
            ];
            if ($existing) {
                $existing->update($data);
                $updated++;
            } else {
                Place::create($data);
                $created++;
            }
        }

        return response()->json([
            'message' => 'Import successful',
            'created' => $created,
            'updated' => $updated,
        ], 201);
    }

    public function clear(): JsonResponse
    {
        DiscoveredUrl::query()->delete();
        Email::query()->delete();
        Place::query()->delete();

        return response()->json(['message' => 'All places, emails and discovered_urls cleared']);
    }
}
