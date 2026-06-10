<?php

namespace Tests\Feature\Api\V1;

use App\Modules\Company\Models\Company;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CompanySearchTest extends TestCase
{
    use RefreshDatabase;

    public function test_search_returns_matching_companies_with_expected_fields(): void
    {
        Company::factory()->create(['name' => 'Acme Plumbing']);
        Company::factory()->create(['name' => 'Acme Roofing']);
        Company::factory()->create(['name' => 'Globex Corp']);

        $response = $this->getJson('/api/v1/companies/search?q=Acme');

        $response->assertOk();

        $names = collect($response->json('data'))->pluck('name')->all();
        $this->assertEqualsCanonicalizing(['Acme Plumbing', 'Acme Roofing'], $names);

        foreach ($response->json('data') as $row) {
            $this->assertArrayHasKey('id', $row);
            $this->assertArrayHasKey('name', $row);
            $this->assertArrayHasKey('status', $row);
            $this->assertArrayHasKey('created_at', $row);
        }
    }

    public function test_q_is_required(): void
    {
        $response = $this->getJson('/api/v1/companies/search');

        $response->assertStatus(422)->assertJsonValidationErrors('q');
    }

    public function test_q_must_be_at_least_two_characters(): void
    {
        $response = $this->getJson('/api/v1/companies/search?q=a');

        $response->assertStatus(422)->assertJsonValidationErrors('q');
    }

    public function test_invalid_status_returns_422(): void
    {
        $response = $this->getJson('/api/v1/companies/search?q=Acme&status=archived');

        $response->assertStatus(422)->assertJsonValidationErrors('status');
    }

    public function test_per_page_above_max_returns_422(): void
    {
        $response = $this->getJson('/api/v1/companies/search?q=Acme&per_page=101');

        $response->assertStatus(422)->assertJsonValidationErrors('per_page');
    }

    public function test_per_page_below_min_returns_422(): void
    {
        $response = $this->getJson('/api/v1/companies/search?q=Acme&per_page=0');

        $response->assertStatus(422)->assertJsonValidationErrors('per_page');
    }

    public function test_search_with_no_matches_returns_empty_results(): void
    {
        Company::factory()->create(['name' => 'Acme Plumbing']);

        $response = $this->getJson('/api/v1/companies/search?q=Zephyr');

        $response->assertOk()
            ->assertJsonCount(0, 'data')
            ->assertJsonPath('total', 0);
    }

    public function test_pagination_respects_per_page(): void
    {
        for ($i = 1; $i <= 5; $i++) {
            Company::factory()->create(['name' => "Acme Co {$i}"]);
        }

        $response = $this->getJson('/api/v1/companies/search?q=Acme&per_page=2');

        $response->assertOk()
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('per_page', 2)
            ->assertJsonPath('total', 5)
            ->assertJsonPath('last_page', 3);
    }

    public function test_status_filter_restricts_results(): void
    {
        Company::factory()->create(['name' => 'Acme Active', 'status' => 'active']);
        Company::factory()->inactive()->create(['name' => 'Acme Inactive']);

        $activeOnly = $this->getJson('/api/v1/companies/search?q=Acme&status=active');
        $activeOnly->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Acme Active');

        $all = $this->getJson('/api/v1/companies/search?q=Acme&status=all');
        $all->assertOk()->assertJsonCount(2, 'data');

        $defaultsToAll = $this->getJson('/api/v1/companies/search?q=Acme');
        $defaultsToAll->assertOk()->assertJsonCount(2, 'data');
    }
}
