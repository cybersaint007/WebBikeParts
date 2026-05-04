@php
    $isEdit = isset($user);
    $action = $isEdit ? route('admin.users.update', $user) : route('admin.users.store');
@endphp

<form method="POST" action="{{ $action }}">
    @csrf
    @if ($isEdit) @method('PUT') @endif

    <div class="mb-3">
        <label class="form-label fw-medium">Name</label>
        <input type="text" name="name" class="form-control @error('name') is-invalid @enderror"
               value="{{ old('name', $user->name ?? '') }}" required>
        @error('name') <div class="invalid-feedback">{{ $message }}</div> @enderror
    </div>

    <div class="mb-3">
        <label class="form-label fw-medium">Email</label>
        <input type="email" name="email" class="form-control @error('email') is-invalid @enderror"
               value="{{ old('email', $user->email ?? '') }}" required>
        @error('email') <div class="invalid-feedback">{{ $message }}</div> @enderror
    </div>

    <div class="mb-3">
        <label class="form-label fw-medium">
            Password @if ($isEdit) <span class="text-muted fs-13">(leave blank to keep current)</span> @endif
        </label>
        <input type="password" name="password" class="form-control @error('password') is-invalid @enderror"
               minlength="8" {{ $isEdit ? '' : 'required' }}>
        @error('password') <div class="invalid-feedback">{{ $message }}</div> @enderror
    </div>

    <div class="mb-3">
        <label class="form-label fw-medium">Confirm password</label>
        <input type="password" name="password_confirmation" class="form-control"
               minlength="8" {{ $isEdit ? '' : 'required' }}>
    </div>

    <div class="d-flex gap-2">
        <button type="submit" class="btn btn-primary">{{ $isEdit ? 'Save changes' : 'Create user' }}</button>
        <a href="{{ route('admin.users.index') }}" class="btn btn-light">Cancel</a>
    </div>
</form>
