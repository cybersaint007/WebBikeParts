@extends('layouts.master')
@section('title', 'Users')

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') Admin @endslot
        @slot('title') Users @endslot
    @endcomponent

    @if (session('status'))
        <div class="alert alert-success">{{ session('status') }}</div>
    @endif

    <div class="card">
        <div class="card-header d-flex align-items-center">
            <h5 class="mb-0 flex-grow-1">All users</h5>
            <a href="{{ route('admin.users.create') }}" class="btn btn-primary">
                <i class="ri-user-add-line me-1"></i> New user
            </a>
        </div>
        <div class="card-body p-0">
            <table class="table mb-0">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th class="text-end">My Bikes</th>
                        <th class="text-end">Watches</th>
                        <th>Created</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($users as $u)
                        <tr>
                            <td>
                                {{ $u->name }}
                                @if ($u->id === auth()->id())
                                    <span class="badge bg-info-subtle text-info ms-1">you</span>
                                @endif
                            </td>
                            <td>{{ $u->email }}</td>
                            <td class="text-end">{{ $u->user_bikes_count }}</td>
                            <td class="text-end">{{ $u->parts_watches_count }}</td>
                            <td>{{ $u->created_at->format('Y-m-d') }}</td>
                            <td class="text-end">
                                <a href="{{ route('admin.users.edit', $u) }}" class="btn btn-sm btn-outline-secondary">Edit</a>
                                @if ($u->id !== auth()->id())
                                    <form method="POST" action="{{ route('admin.users.destroy', $u) }}" class="d-inline ms-1">
                                        @csrf @method('DELETE')
                                        <button type="submit" class="btn btn-sm btn-outline-danger"
                                                onclick="return confirm('Delete {{ $u->email }}? Their My Bikes and watches will be removed.')">
                                            Delete
                                        </button>
                                    </form>
                                @endif
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
        @if ($users->hasPages())
            <div class="card-footer">{{ $users->links() }}</div>
        @endif
    </div>
@endsection
