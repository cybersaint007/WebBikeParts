@extends('layouts.master')
@section('title', __('Profile'))

@section('content')
    @component('components.breadcrumb')
        @slot('li_1') {{ __('Account') }} @endslot
        @slot('title') {{ __('Profile') }} @endslot
    @endcomponent

    @if (session('status'))
        <div class="alert alert-success" role="alert">{{ session('status') }}</div>
    @endif

    <div class="row justify-content-center">
        <div class="col-lg-4">
            <div class="card">
                <div class="card-body text-center">
                    <img src="@if ($user->avatar) {{ URL::asset('images/' . $user->avatar) }}@else{{ URL::asset('build/images/users/avatar-1.jpg') }} @endif"
                         class="rounded-circle avatar-xl img-thumbnail mb-3" alt="">
                    <h5 class="fs-17 mb-1">{{ $user->name }}</h5>
                    <p class="text-muted mb-0">{{ $user->email }}</p>
                    <p class="text-muted mt-2 mb-0">
                        <span class="badge bg-{{ $user->isAdmin() ? 'primary' : 'secondary' }}">
                            {{ $user->isAdmin() ? __('Admin') : __('User') }}
                        </span>
                    </p>
                </div>
            </div>
        </div>

        <div class="col-lg-8">
            <div class="card">
                <div class="card-header"><h5 class="mb-0">{{ __('Edit profile') }}</h5></div>
                <div class="card-body">
                    <form method="POST" action="{{ route('profile.update') }}" enctype="multipart/form-data">
                        @csrf
                        @method('PATCH')

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Name') }}</label>
                            <input type="text" name="name" class="form-control @error('name') is-invalid @enderror"
                                   value="{{ old('name', $user->name) }}" required>
                            @error('name') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Email') }}</label>
                            <input type="email" name="email" class="form-control @error('email') is-invalid @enderror"
                                   value="{{ old('email', $user->email) }}" required>
                            @error('email') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Avatar') }}</label>
                            <input type="file" name="avatar" accept="image/png,image/jpeg"
                                   class="form-control @error('avatar') is-invalid @enderror">
                            <div class="form-text">{{ __('PNG or JPG, up to 1 MB.') }}</div>
                            @error('avatar') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <button type="submit" class="btn btn-primary">{{ __('Save changes') }}</button>
                    </form>
                </div>
            </div>

            <div class="card">
                <div class="card-header"><h5 class="mb-0">{{ __('Change password') }}</h5></div>
                <div class="card-body">
                    <form method="POST" action="{{ route('profile.password') }}">
                        @csrf
                        @method('PATCH')

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Current password') }}</label>
                            <input type="password" name="current_password"
                                   class="form-control @error('current_password') is-invalid @enderror" required>
                            @error('current_password') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('New password') }}</label>
                            <input type="password" name="password"
                                   class="form-control @error('password') is-invalid @enderror" minlength="8" required>
                            @error('password') <div class="invalid-feedback">{{ $message }}</div> @enderror
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-medium">{{ __('Confirm new password') }}</label>
                            <input type="password" name="password_confirmation"
                                   class="form-control" minlength="8" required>
                        </div>

                        <button type="submit" class="btn btn-primary">{{ __('Update password') }}</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
@endsection
