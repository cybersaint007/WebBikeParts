@extends('layouts.master')
@section('title', __('Login History') . ' — ' . $user->email)

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') <a href="{{ route('admin.users.index') }}">{{ __('Users') }}</a> @endslot
        @slot('title') {{ __('Login History') }} — {{ $user->email }} @endslot
    @endcomponent

    <div class="card">
        <div class="card-header d-flex align-items-center">
            <h5 class="mb-0 flex-grow-1">
                {{ __('Login History') }}
                <span class="text-muted fw-normal fs-6 ms-1">{{ $user->name }}</span>
            </h5>
            <a href="{{ route('admin.users.edit', $user) }}" class="btn btn-sm btn-outline-secondary">
                {{ __('Edit user') }}
            </a>
        </div>
        <div class="card-body p-0">
            <table class="table mb-0">
                <thead>
                    <tr>
                        <th>{{ __('When') }}</th>
                        <th>{{ __('Status') }}</th>
                        <th>{{ __('IP Address') }}</th>
                        <th>{{ __('User Agent') }}</th>
                        <th>{{ __('Logout') }}</th>
                        <th>{{ __('Duration') }}</th>
                    </tr>
                </thead>
                <tbody>
                    @forelse ($histories as $h)
                        <tr>
                            <td class="text-nowrap">{{ $h->login_at->format('Y-m-d H:i:s') }}</td>
                            <td>
                                @if ($h->success)
                                    <span class="badge bg-success-subtle text-success">{{ __('Success') }}</span>
                                @else
                                    <span class="badge bg-danger-subtle text-danger">{{ __('Failed') }}</span>
                                @endif
                            </td>
                            <td class="text-nowrap">{{ $h->ip_address ?? '—' }}</td>
                            <td class="text-muted small" style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                                title="{{ $h->user_agent }}">
                                {{ $h->user_agent ?? '—' }}
                            </td>
                            <td class="text-nowrap">
                                {{ $h->logout_at ? $h->logout_at->format('H:i:s') : '—' }}
                            </td>
                            <td class="text-nowrap">{{ $h->duration() ?? '—' }}</td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="6" class="text-center text-muted py-4">{{ __('No login history yet.') }}</td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
        @if ($histories->hasPages())
            <div class="card-footer">{{ $histories->links() }}</div>
        @endif
    </div>
@endsection
