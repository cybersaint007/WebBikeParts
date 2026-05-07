<!-- ========== App Menu ========== -->
<div class="app-menu navbar-menu">
    <!-- LOGO -->
    <div class="navbar-brand-box">
        <!-- Dark Logo-->
        <a href="index" class="logo logo-dark">
            <span class="logo-sm">
                <img src="{{ URL::asset('build/images/logo-sm.png') }}" alt="" height="22">
            </span>
            <span class="logo-lg">
                <img src="{{ URL::asset('build/images/logo-dark.png') }}" alt="" height="17">
            </span>
        </a>
        <!-- Light Logo-->
        <a href="index" class="logo logo-light">
            <span class="logo-sm">
                <img src="{{ URL::asset('build/images/logo-sm.png') }}" alt="" height="22">
            </span>
            <span class="logo-lg">
                <img src="{{ URL::asset('build/images/logo-light.png') }}" alt="" height="17">
            </span>
        </a>
        <button type="button" class="btn btn-sm p-0 fs-20 header-item float-end btn-vertical-sm-hover"
            id="vertical-hover">
            <i class="ri-record-circle-line"></i>
        </button>
    </div>

    <div id="scrollbar">
        <div class="container-fluid">

            <div id="two-column-menu">
            </div>
            <ul class="navbar-nav" id="navbar-nav">
                @auth
                <li class="menu-title"><span>{{ __('Crawler') }}</span></li>
                <li class="nav-item">
                    <a class="nav-link menu-link {{ request()->routeIs('parts.*') ? 'active' : '' }}"
                       href="{{ route('parts.index') }}">
                        <i class="ri-shopping-bag-line"></i> <span>{{ __('Parts') }}</span>
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link menu-link {{ request()->routeIs('my-bikes.*') ? 'active' : '' }}"
                       href="{{ route('my-bikes.index') }}">
                        <i class="ri-motorbike-line"></i> <span>{{ __('My Bikes') }}</span>
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link menu-link {{ request()->routeIs('watch-list.*') ? 'active' : '' }}"
                       href="{{ route('watch-list.index') }}">
                        <i class="ri-eye-line"></i> <span>{{ __('Watch List') }}</span>
                    </a>
                </li>
                @if (auth()->user()?->isAdmin())
                <li class="menu-title"><span>{{ __('Admin') }}</span></li>
                <li class="nav-item">
                    <a class="nav-link menu-link {{ request()->routeIs('admin.users.*') ? 'active' : '' }}"
                       href="{{ route('admin.users.index') }}">
                        <i class="ri-user-settings-line"></i> <span>{{ __('Users') }}</span>
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link menu-link {{ request()->routeIs('admin.adapters.*') ? 'active' : '' }}"
                       href="{{ route('admin.adapters.index') }}">
                        <i class="ri-pulse-line"></i> <span>{{ __('Adapter Status') }}</span>
                    </a>
                </li>
                @endif
                @endauth

            </ul>
        </div>
        <!-- Sidebar -->
    </div>
    <div class="sidebar-background"></div>
</div>
<!-- Left Sidebar End -->
<!-- Vertical Overlay-->
<div class="vertical-overlay"></div>
