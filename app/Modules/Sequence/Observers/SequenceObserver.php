<?php

namespace App\Modules\Sequence\Observers;

use App\Modules\Sequence\Models\Sequence;
use App\Jobs\Notifications\NotifySequenceUpdate;

class SequenceObserver
{
    public function updated(Sequence $sequence): void
    {
        // Invariant: terminal sequences (cancelled, recovered) never receive
        // notifications.
        if ($sequence->isTerminal()) {
            return;
        }

        NotifySequenceUpdate::dispatch($sequence->id);
    }
}
