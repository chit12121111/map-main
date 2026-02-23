<?php

namespace App\Http\Controllers;

use App\Models\DiscoveredUrl;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class DiscoveredUrlController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $query = DiscoveredUrl::query()->orderByDesc('created_at');
        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }
        if ($request->filled('place_id')) {
            $query->where('place_id', $request->place_id);
        }
        if ($request->filled('url_type')) {
            $query->where('url_type', $request->url_type);
        }
        $perPage = (int) $request->get('per_page', 200);
        $items = $query->paginate($perPage);

        return response()->json([
            'data' => $items->items(),
            'total' => $items->total(),
            'per_page' => $items->perPage(),
            'current_page' => $items->currentPage(),
        ]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'place_id' => 'required|string',
            'url' => 'required|string',
            'url_type' => 'required|string|in:FACEBOOK,WEBSITE',
            'found_by_stage' => 'required|string|in:STAGE2,STAGE3',
            'status' => 'nullable|string',
        ]);
        $data['status'] = $data['status'] ?? 'NEW';

        $item = DiscoveredUrl::firstOrCreate(
            ['place_id' => $data['place_id'], 'url' => $data['url']],
            $data
        );

        return response()->json($item, 201);
    }

    public function show(int $discovered_url): JsonResponse
    {
        $model = DiscoveredUrl::findOrFail($discovered_url);

        return response()->json($model);
    }

    public function update(Request $request, int $discovered_url): JsonResponse
    {
        $model = DiscoveredUrl::findOrFail($discovered_url);
        $model->update($request->only(['status']));

        return response()->json($model);
    }

    public function destroy(int $discovered_url): JsonResponse
    {
        DiscoveredUrl::findOrFail($discovered_url)->delete();

        return response()->json(['message' => 'Deleted'], 200);
    }
}
