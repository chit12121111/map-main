<?php

namespace App\Http\Controllers;

use App\Models\DiscoveredUrl;
use App\Models\Email;
use App\Models\Place;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class PlaceController extends Controller
{
    private function cleanThaiPrefix(?string $value, string $prefix): ?string
    {
        if (! $value) {
            return null;
        }
        $trimmed = trim($value);
        if ($trimmed === '') {
            return null;
        }
        return preg_replace('/^'.preg_quote($prefix, '/').'\s*/u', '', $trimmed) ?: $trimmed;
    }

    private function inferProvinceFromAddress(?string $address): ?string
    {
        if (! $address) {
            return null;
        }
        $text = trim($address);
        if ($text === '') {
            return null;
        }
        if (preg_match('/(กรุงเทพมหานคร|กรุงเทพฯ)/u', $text, $m)) {
            return $m[1] === 'กรุงเทพฯ' ? 'กรุงเทพมหานคร' : $m[1];
        }
        if (preg_match('/จังหวัด\s*([^\s,]+)/u', $text, $m)) {
            return $this->cleanThaiPrefix($m[0], 'จังหวัด');
        }

        return null;
    }

    private function inferDistrictFromAddress(?string $address): ?string
    {
        if (! $address) {
            return null;
        }
        $text = trim($address);
        if ($text === '') {
            return null;
        }
        if (preg_match('/เขต\s*([^\s,]+)/u', $text, $m)) {
            return $this->cleanThaiPrefix($m[0], 'เขต');
        }
        if (preg_match('/อำเภอ\s*([^\s,]+)/u', $text, $m)) {
            return $this->cleanThaiPrefix($m[0], 'อำเภอ');
        }

        return null;
    }

    private function inferCategoryName(array $row): ?string
    {
        $rawCategory = trim((string) ($row['normalized_category'] ?? $row['category'] ?? ''));
        if ($rawCategory !== '') {
            return $rawCategory;
        }
        $hint = mb_strtolower(trim((string) ($row['name'] ?? $row['title'] ?? '')), 'UTF-8');
        if ($hint === '') {
            return null;
        }
        $map = [
            'apartment' => 'Apartment',
            'condo' => 'Condo',
            'hotel' => 'Hotel',
            'restaurant' => 'Restaurant',
            'cafe' => 'Cafe',
            'coffee' => 'Cafe',
            'clinic' => 'Clinic',
            'hospital' => 'Hospital',
            'school' => 'School',
            'mall' => 'Mall',
            'shop' => 'Shop',
            'ร้านอาหาร' => 'Restaurant',
            'คาเฟ่' => 'Cafe',
            'กาแฟ' => 'Cafe',
            'โรงแรม' => 'Hotel',
            'อพาร์ตเมนต์' => 'Apartment',
            'อพาร์ทเม้นท์' => 'Apartment',
            'คอนโด' => 'Condo',
            'คลินิก' => 'Clinic',
            'โรงพยาบาล' => 'Hospital',
            'โรงเรียน' => 'School',
            'ห้าง' => 'Mall',
            'ร้าน' => 'Shop',
        ];
        foreach ($map as $needle => $label) {
            if (str_contains($hint, $needle)) {
                return $label;
            }
        }

        return null;
    }

    private function normalizeDedupText(?string $value): string
    {
        if (! $value) {
            return '';
        }
        $lower = mb_strtolower(trim($value), 'UTF-8');
        if ($lower === '') {
            return '';
        }

        return preg_replace('/\s+/u', ' ', $lower) ?: $lower;
    }

    public function index(Request $request): JsonResponse
    {
        $query = Place::query()->orderBy('name');
        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }
        if ($request->filled('province')) {
            $query->where('province', $request->province);
        }
        if ($request->filled('district')) {
            $query->where('district', $request->district);
        }
        if ($request->filled('category')) {
            $query->where('category', $request->category);
        }
        if ($request->filled('normalized_category')) {
            $query->where('normalized_category', $request->normalized_category);
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
            'province' => 'nullable|string',
            'district' => 'nullable|string',
            'normalized_category' => 'nullable|string',
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
        $data = $request->only([
            'status',
            'name',
            'website',
            'phone',
            'address',
            'category',
            'normalized_category',
            'province',
            'district',
        ]);
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
            $address = $row['address'] ?? null;
            $website = $row['website'] ?? $row['url'] ?? null;
            $inferredCategory = $this->inferCategoryName($row);
            $inferredProvince = $this->inferProvinceFromAddress($address);
            $inferredDistrict = $this->inferDistrictFromAddress($address);
            $normalizedName = $this->normalizeDedupText($name);
            $normalizedAddress = $this->normalizeDedupText($address);

            // Duplicate guard for unstable place_id rows:
            // prefer matching by website, then by normalized name+address.
            if (! $existing && $website) {
                $existing = Place::query()->where('website', $website)->first();
            }
            if (! $existing && $normalizedName !== '' && $normalizedAddress !== '') {
                $existing = Place::query()
                    ->whereRaw('LOWER(TRIM(name)) = ?', [$normalizedName])
                    ->whereRaw('LOWER(TRIM(address)) = ?', [$normalizedAddress])
                    ->first();
            }

            $data = [
                'place_id' => $existing?->place_id ?? $placeId,
                'name' => $name,
                'website' => $website,
                'phone' => $row['phone'] ?? null,
                'google_maps_url' => $row['google_maps_url'] ?? $row['url'] ?? $website ?? '',
                'address' => $address,
                'category' => $inferredCategory,
                'normalized_category' => $inferredCategory,
                'province' => $row['province'] ?? $inferredProvince,
                'district' => $row['district'] ?? $inferredDistrict,
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
