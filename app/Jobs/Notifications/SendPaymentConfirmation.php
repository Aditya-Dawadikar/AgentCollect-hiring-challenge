<?php

namespace App\Jobs\Notifications;

use App\Mail\PaymentConfirmationMail;
use App\Modules\Payment\Models\UserPayment;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;

class SendPaymentConfirmation implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    // Status gate: only sequences still being actively chased should
    // generate a payment confirmation email to the debtor.
    public const ALLOWED_SEQUENCE_STATUSES = ['active', 'installment'];

    public function __construct(public int $paymentId) {}

    public function handle(): void
    {
        $payment = UserPayment::with('sequence')->findOrFail($this->paymentId);
        $sequence = $payment->sequence;

        if (! in_array($sequence->status, self::ALLOWED_SEQUENCE_STATUSES, true)) {
            Log::info('Skipping payment confirmation: sequence status not eligible', [
                'payment_id' => $payment->id,
                'sequence_id' => $sequence->id,
                'status' => $sequence->status,
            ]);

            return;
        }

        Mail::to($sequence->company->email)->send(new PaymentConfirmationMail($payment));
    }
}
