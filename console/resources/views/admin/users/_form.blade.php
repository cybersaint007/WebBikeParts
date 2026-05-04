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

    @php
        $currentRole = old('role', $user->role ?? \App\Models\User::ROLE_USER);
        $isSelf = $isEdit && isset($user) && $user->id === auth()->id();
    @endphp
    <div class="mb-3">
        <label class="form-label fw-medium">Role</label>
        <select name="role" class="form-select @error('role') is-invalid @enderror" required>
            <option value="{{ \App\Models\User::ROLE_USER }}"  @selected($currentRole === \App\Models\User::ROLE_USER)>User</option>
            <option value="{{ \App\Models\User::ROLE_ADMIN }}" @selected($currentRole === \App\Models\User::ROLE_ADMIN)>Admin</option>
        </select>
        @if ($isSelf)
            <div class="form-text text-warning">You can't demote yourself.</div>
        @else
            <div class="form-text">Admins can view adapter status and manage users.</div>
        @endif
        @error('role') <div class="invalid-feedback">{{ $message }}</div> @enderror
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
