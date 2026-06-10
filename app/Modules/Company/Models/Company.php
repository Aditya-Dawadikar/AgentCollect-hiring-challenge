<?php

namespace App\Modules\Company\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Company extends Model
{
    use HasFactory;

    protected $fillable = ['name', 'email', 'status'];

    protected $casts = [
        'status' => 'string',
    ];

    public function scopeSearch($query, string $term)
    {
        return $query->where('name', 'like', "%{$term}%");
    }

    public function scopeWithStatus($query, ?string $status)
    {
        return $query->when(
            $status && $status !== 'all',
            fn ($query) => $query->where('status', $status)
        );
    }

    public function sequences()
    {
        return $this->hasMany(\App\Modules\Sequence\Models\Sequence::class);
    }

    protected static function newFactory()
    {
        return \Database\Factories\CompanyFactory::new();
    }
}
