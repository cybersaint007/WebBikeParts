@extends('layouts.master')
@section('title', 'Edit user')

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') <a href="{{ route('admin.users.index') }}">Users</a> @endslot
        @slot('title') Edit {{ $user->email }} @endslot
    @endcomponent

    <div class="row justify-content-center">
        <div class="col-lg-6">
            <div class="card">
                <div class="card-header"><h5 class="mb-0">Edit user</h5></div>
                <div class="card-body">
                    @include('admin.users._form')
                </div>
            </div>
        </div>
    </div>
@endsection
