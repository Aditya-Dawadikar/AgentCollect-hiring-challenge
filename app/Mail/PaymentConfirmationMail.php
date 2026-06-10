<?php

namespace App\Mail;

use App\Modules\Payment\Models\UserPayment;
use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;
use Illuminate\Queue\SerializesModels;

class PaymentConfirmationMail extends Mailable
{
    use Queueable, SerializesModels;

    public function __construct(public UserPayment $payment) {}

    public function envelope(): Envelope
    {
        return new Envelope(
            subject: 'Payment received - thank you',
        );
    }

    public function content(): Content
    {
        return new Content(
            htmlString: sprintf(
                '<p>We received your payment of %s %s. Thank you for your business.</p>',
                number_format((float) $this->payment->amount, 2),
                $this->payment->currency,
            ),
        );
    }
}
