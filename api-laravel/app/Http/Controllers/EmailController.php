<?php

namespace App\Http\Controllers;

use App\Models\Email;
use App\Models\Place;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class EmailController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $query = Email::query()->orderByDesc('created_at');
        if ($request->filled('place_id')) {
            $query->where('place_id', $request->place_id);
        }
        if ($request->filled('source')) {
            $query->where('source', $request->source);
        }
        if ($request->boolean('include_place')) {
            $query->with('place');
        }
        $perPage = (int) $request->get('per_page', 500);
        $emails = $query->paginate($perPage);
        $data = $emails->items();
        if ($request->boolean('include_place')) {
            $data = array_map(function ($email) {
                $arr = $email->toArray();
                $arr['place'] = $email->place ? $email->place->toArray() : null;
                return $arr;
            }, $data);
        }

        return response()->json([
            'data' => $data,
            'total' => $emails->total(),
            'per_page' => $emails->perPage(),
            'current_page' => $emails->currentPage(),
        ]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'place_id' => 'required|string',
            'email' => 'required|email',
            'source' => 'required|string',
        ]);

        $email = Email::firstOrCreate(
            ['place_id' => $data['place_id'], 'email' => $data['email']],
            ['source' => $data['source']]
        );
        // Keep place status in sync with discovered contacts.
        Place::query()
            ->where('place_id', $data['place_id'])
            ->update(['status' => 'DONE']);

        return response()->json($email, 201);
    }

    public function show(int $email): JsonResponse
    {
        $model = Email::findOrFail($email);

        return response()->json($model);
    }

    public function update(Request $request, int $email): JsonResponse
    {
        $model = Email::findOrFail($email);
        $model->update($request->only(['source', 'category', 'is_valid']));

        return response()->json($model);
    }

    public function destroy(int $email): JsonResponse
    {
        Email::findOrFail($email)->delete();

        return response()->json(['message' => 'Deleted'], 200);
    }

    public function bulkDelete(Request $request): JsonResponse
    {
        $ids = $request->input('ids', []);
        if (! is_array($ids)) {
            return response()->json(['error' => 'ids must be an array'], 422);
        }
        $count = Email::whereIn('id', $ids)->delete();

        return response()->json(['message' => "Deleted {$count} emails", 'deleted' => $count]);
    }
}
