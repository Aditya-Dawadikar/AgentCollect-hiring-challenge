<?php

namespace Tests\Unit\Flows;

use App\Jobs\Notifications\SendPaymentConfirmation;
use App\Mail\PaymentConfirmationMail;
use App\Modules\Payment\Models\UserPayment;
use App\Modules\Sequence\Models\Sequence;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class PaymentConfirmationFlowTest extends TestCase
{
    use RefreshDatabase;

    public function test_completed_payment_dispatches_confirmation_job(): void
    {
        Queue::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        $payment = UserPayment::factory()->for($sequence, 'sequence')->create(['status' => 'completed']);

        Queue::assertPushed(
            SendPaymentConfirmation::class,
            fn (SendPaymentConfirmation $job) => $job->paymentId === $payment->id
        );
    }

    public function test_pending_payment_does_not_dispatch_confirmation_job(): void
    {
        Queue::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        UserPayment::factory()->pending()->for($sequence, 'sequence')->create();

        Queue::assertNotPushed(SendPaymentConfirmation::class);
    }

    public function test_payment_on_active_sequence_sends_confirmation_email(): void
    {
        Mail::fake();

        $sequence = Sequence::factory()->create(['status' => 'active']);
        $payment = UserPayment::factory()->for($sequence, 'sequence')->create(['status' => 'completed']);

        Mail::assertSent(
            PaymentConfirmationMail::class,
            fn (PaymentConfirmationMail $mail) => $mail->payment->id === $payment->id
        );
    }

    public function test_payment_on_cancelled_sequence_does_not_send_confirmation_email(): void
    {
        Mail::fake();

        $sequence = Sequence::factory()->cancelled()->create();
        UserPayment::factory()->for($sequence, 'sequence')->create(['status' => 'completed']);

        Mail::assertNotSent(PaymentConfirmationMail::class);
    }

    public function test_job_logs_skip_reason_when_sequence_status_not_eligible(): void
    {
        Mail::fake();

        $sequence = Sequence::factory()->cancelled()->create();

        Log::shouldReceive('info')
            ->once()
            ->withArgs(function (string $message, array $context) use ($sequence) {
                return $message === 'Skipping payment confirmation: sequence status not eligible'
                    && $context['sequence_id'] === $sequence->id
                    && $context['status'] === 'cancelled';
            });

        UserPayment::factory()->for($sequence, 'sequence')->create(['status' => 'completed']);
    }
}
