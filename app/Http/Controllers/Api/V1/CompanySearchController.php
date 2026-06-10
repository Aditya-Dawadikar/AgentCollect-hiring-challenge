<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Modules\Company\Models\Company;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CompanySearchController extends Controller
{
    public function __invoke(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'q' => ['required', 'string', 'min:2'],
            'status' => ['nullable', 'string', 'in:active,inactive,all'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
        ]);

        $companies = Company::query()
            ->search($validated['q'])
            ->withStatus($validated['status'] ?? 'all')
            ->orderBy('name')
            ->paginate($validated['per_page'] ?? 15)
            ->through(fn (Company $company) => [
                'id' => $company->id,
                'name' => $company->name,
                'status' => $company->status,
                'created_at' => $company->created_at,
            ]);

        return response()->json($companies);
    }
}
