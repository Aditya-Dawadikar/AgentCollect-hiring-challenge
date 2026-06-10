<?php

namespace Tests\Unit\Flows;

use App\Jobs\Notifications\NotifySequenceUpdate;
use App\Modules\Sequence\Models\Sequence;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class SequenceNotificationFlowTest extends TestCase
{
    use RefreshDatabase;

    public function test_cancelled_sequence_does_not_dispatch_notification(): void
    {
        Queue::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        $sequence->update(['status' => 'cancelled']);

        Queue::assertNotPushed(NotifySequenceUpdate::class);
    }

    public function test_recovered_sequence_does_not_dispatch_notification(): void
    {
        Queue::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        $sequence->update(['status' => 'recovered']);

        Queue::assertNotPushed(NotifySequenceUpdate::class);
    }

    public function test_active_sequence_update_dispatches_notification(): void
    {
        Queue::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        $sequence->update(['amount' => 999.99]);

        Queue::assertPushed(
            NotifySequenceUpdate::class,
            fn (NotifySequenceUpdate $job) => $job->sequenceId === $sequence->id
        );
    }

    public function test_job_skips_terminal_sequence_as_safety_net(): void
    {
        $sequence = Sequence::factory()->cancelled()->create();

        Log::shouldReceive('info')
            ->once()
            ->with('Skipping sequence update notification: terminal status', [
                'sequence_id' => $sequence->id,
                'status' => $sequence->status,
            ]);

        (new NotifySequenceUpdate($sequence->id))->handle();
    }

    public function test_job_sends_notification_for_active_sequence(): void
    {
        $sequence = Sequence::factory()->create(['status' => 'active']);

        Log::shouldReceive('info')
            ->once()
            ->with('Sending sequence update notification', [
                'sequence_id' => $sequence->id,
                'status' => $sequence->status,
            ]);

        (new NotifySequenceUpdate($sequence->id))->handle();
    }
}
