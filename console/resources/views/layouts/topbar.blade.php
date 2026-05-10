<header id="page-topbar">
    <div class="layout-width">
        <div class="navbar-header">
            <div class="d-flex">
                <!-- LOGO -->
                <div class="navbar-brand-box horizontal-logo">
                    <a href="{{ route('my-bikes.index') }}" class="logo logo-dark text-dark text-decoration-none">
                        <span class="logo-sm">
                            <i class="ri-tools-fill fs-4"></i>
                        </span>
                        <span class="logo-lg fw-bold fs-5">
                            <i class="ri-tools-fill me-1"></i>Bike Parts
                        </span>
                    </a>

                    <a href="{{ route('my-bikes.index') }}" class="logo logo-light text-white text-decoration-none">
                        <span class="logo-sm">
                            <i class="ri-tools-fill fs-4"></i>
                        </span>
                        <span class="logo-lg fw-bold fs-5">
                            <i class="ri-tools-fill me-1"></i>Bike Parts
                        </span>
                    </a>
                </div>

                <button type="button" class="btn btn-sm px-3 fs-16 header-item vertical-menu-btn topnav-hamburger" id="topnav-hamburger-icon">
                    <span class="hamburger-icon">
                        <span></span>
                        <span></span>
                        <span></span>
                    </span>
                </button>

                <!-- App Search-->
                <form class="app-search d-none d-md-block">
                    <div class="position-relative">
                        <input type="text" class="form-control" placeholder="{{ __('Search...') }}" autocomplete="off" id="search-options" value="">
                        <span class="mdi mdi-magnify search-widget-icon"></span>
                        <span class="mdi mdi-close-circle search-widget-icon search-widget-icon-close d-none" id="search-close-options"></span>
                    </div>
                    <div class="dropdown-menu dropdown-menu-lg" id="search-dropdown">
                        <div data-simplebar style="max-height: 320px;">
                            <!-- item-->
                            <div class="dropdown-header">
                                <h6 class="text-overflow text-muted mb-0 text-uppercase">Recent Searches</h6>
                            </div>

                            <div class="dropdown-item bg-transparent text-wrap">
                                <a href="index" class="btn btn-soft-secondary btn-sm rounded-pill">how to setup <i class="mdi mdi-magnify ms-1"></i></a>
                                <a href="index" class="btn btn-soft-secondary btn-sm rounded-pill">buttons <i class="mdi mdi-magnify ms-1"></i></a>
                            </div>
                            <!-- item-->
                            <div class="dropdown-header mt-2">
                                <h6 class="text-overflow text-muted mb-1 text-uppercase">Pages</h6>
                            </div>

                            <!-- item-->
                            <a href="javascript:void(0);" class="dropdown-item notify-item">
                                <i class="ri-bubble-chart-line align-middle fs-18 text-muted me-2"></i>
                                <span>Analytics Dashboard</span>
                            </a>

                            <!-- item-->
                            <a href="javascript:void(0);" class="dropdown-item notify-item">
                                <i class="ri-lifebuoy-line align-middle fs-18 text-muted me-2"></i>
                                <span>Help Center</span>
                            </a>

                            <!-- item-->
                            <a href="javascript:void(0);" class="dropdown-item notify-item">
                                <i class="ri-user-settings-line align-middle fs-18 text-muted me-2"></i>
                                <span>My account settings</span>
                            </a>

                            <!-- item-->
                            <div class="dropdown-header mt-2">
                                <h6 class="text-overflow text-muted mb-2 text-uppercase">Members</h6>
                            </div>

                            <div class="notification-list">
                                <!-- item -->
                                <a href="javascript:void(0);" class="dropdown-item notify-item py-2">
                                    <div class="d-flex">
                                        <img src="{{ URL::asset('build/images/users/avatar-2.jpg') }}" class="me-3 rounded-circle avatar-xs" alt="user-pic">
                                        <div class="flex-grow-1">
                                            <h6 class="m-0">Angela Bernier</h6>
                                            <span class="fs-11 mb-0 text-muted">Manager</span>
                                        </div>
                                    </div>
                                </a>
                                <!-- item -->
                                <a href="javascript:void(0);" class="dropdown-item notify-item py-2">
                                    <div class="d-flex">
                                        <img src="{{ URL::asset('build/images/users/avatar-3.jpg') }}" class="me-3 rounded-circle avatar-xs" alt="user-pic">
                                        <div class="flex-grow-1">
                                            <h6 class="m-0">David Grasso</h6>
                                            <span class="fs-11 mb-0 text-muted">Web Designer</span>
                                        </div>
                                    </div>
                                </a>
                                <!-- item -->
                                <a href="javascript:void(0);" class="dropdown-item notify-item py-2">
                                    <div class="d-flex">
                                        <img src="{{ URL::asset('build/images/users/avatar-5.jpg') }}" class="me-3 rounded-circle avatar-xs" alt="user-pic">
                                        <div class="flex-grow-1">
                                            <h6 class="m-0">Mike Bunch</h6>
                                            <span class="fs-11 mb-0 text-muted">React Developer</span>
                                        </div>
                                    </div>
                                </a>
                            </div>
                        </div>

                        <div class="text-center pt-3 pb-1">
                            <a href="pages-search-results" class="btn btn-primary btn-sm">View All Results <i class="ri-arrow-right-line ms-1"></i></a>
                        </div>
                    </div>
                </form>
            </div>

            <div class="d-flex align-items-center">

                <div class="dropdown d-md-none topbar-head-dropdown header-item">
                    <button type="button" class="btn btn-icon btn-topbar btn-ghost-secondary rounded-circle" id="page-header-search-dropdown" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                        <i class="bx bx-search fs-22"></i>
                    </button>
                    <div class="dropdown-menu dropdown-menu-lg dropdown-menu-end p-0" aria-labelledby="page-header-search-dropdown">
                        <form class="p-3">
                            <div class="form-group m-0">
                                <div class="input-group">
                                    <input type="text" class="form-control" placeholder="{{ __('Search ...') }}" aria-label="Recipient's username">
                                    <button class="btn btn-primary" type="submit"><i class="mdi mdi-magnify"></i></button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <div class="dropdown ms-1 topbar-head-dropdown header-item">
                    <button type="button" class="btn btn-icon btn-topbar btn-ghost-secondary rounded-circle" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                        @switch(app()->getLocale())
                            @case('ja')
                                <span class="fw-semibold">JA</span>
                                @break
                            @case('zh-TW')
                                <span class="fw-semibold">繁</span>
                                @break
                            @default
                                <span class="fw-semibold">EN</span>
                        @endswitch
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <a href="{{ url('index/en') }}" class="dropdown-item notify-item language py-2 @if(app()->getLocale()==='en') active @endif" data-lang="en" title="English">
                            <span class="align-middle">English</span>
                        </a>
                        <a href="{{ url('index/ja') }}" class="dropdown-item notify-item language py-2 @if(app()->getLocale()==='ja') active @endif" data-lang="ja" title="Japanese">
                            <span class="align-middle">日本語</span>
                        </a>
                        <a href="{{ url('index/zh-TW') }}" class="dropdown-item notify-item language py-2 @if(app()->getLocale()==='zh-TW') active @endif" data-lang="zh-TW" title="Traditional Chinese">
                            <span class="align-middle">繁體中文</span>
                        </a>
                    </div>
                </div>

                <div class="ms-1 header-item d-none d-sm-flex">
                    <button type="button" class="btn btn-icon btn-topbar btn-ghost-secondary rounded-circle" id="topbar-fullscreen-btn" data-toggle="fullscreen">
                        <i class='bx bx-fullscreen fs-22'></i>
                    </button>
                </div>

                <div class="ms-1 header-item d-none d-sm-flex">
                    <button type="button" class="btn btn-icon btn-topbar btn-ghost-secondary rounded-circle light-dark-mode" id="topbar-theme-btn">
                        <i class='bx bx-moon fs-22'></i>
                    </button>
                </div>


                <div class="dropdown ms-sm-3 header-item topbar-user">
                    <button type="button" class="btn" id="page-header-user-dropdown" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                        <span class="d-flex align-items-center">
                            <img class="rounded-circle header-profile-user" src="@if (Auth::user()->avatar != '') {{ URL::asset('bike-images/avatars/' . Auth::user()->avatar) }}@else{{ URL::asset('build/images/users/avatar-1.jpg') }} @endif" alt="Header Avatar">
                            <span class="text-start ms-xl-2">
                                <span class="d-none d-xl-inline-block ms-1 fw-medium user-name-text">{{ Auth::user()->name }}</span>
                                <span class="d-none d-xl-block ms-1 fs-12 user-name-sub-text">Founder</span>
                            </span>
                        </span>
                    </button>
                    <div class="dropdown-menu dropdown-menu-end">
                        <a class="dropdown-item" href="{{ route('profile.show') }}"><i class="mdi mdi-account-circle text-muted fs-16 align-middle me-1"></i> <span class="align-middle">{{ __('Profile') }}</span></a>
                        <a class="dropdown-item " href="javascript:void();" onclick="event.preventDefault(); document.getElementById('logout-form').submit();"><i class="bx bx-power-off font-size-16 align-middle me-1"></i> <span>{{ __('Logout') }}</span></a>
                        <form id="logout-form" action="{{ route('logout') }}" method="POST" style="display: none;">
                            @csrf
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</header>

<script>
(function () {
    function toggleTheme() {
        var html = document.documentElement;
        var next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', next);
        try { sessionStorage.setItem('data-bs-theme', next); } catch (e) {}
        var icon = document.querySelector('#topbar-theme-btn i');
        if (icon) {
            icon.classList.toggle('bx-moon', next === 'light');
            icon.classList.toggle('bx-sun', next === 'dark');
        }
    }

    function toggleFullscreen() {
        document.body.classList.toggle('fullscreen-enable');
        var d = document, e = d.documentElement;
        var inFs = d.fullscreenElement || d.webkitFullscreenElement || d.mozFullScreenElement;
        if (!inFs) {
            (e.requestFullscreen || e.webkitRequestFullscreen || e.mozRequestFullScreen).call(e);
        } else {
            (d.exitFullscreen || d.webkitExitFullscreen || d.mozCancelFullScreen).call(d);
        }
    }

    function bind(el, handler) {
        if (!el || el.dataset.topbarBound === '1') return;
        el.dataset.topbarBound = '1';
        el.addEventListener('click', function (ev) { ev.preventDefault(); handler(); });
    }

    function init() {
        bind(document.getElementById('topbar-fullscreen-btn'), toggleFullscreen);
        bind(document.getElementById('topbar-theme-btn'), toggleTheme);

        var saved = null;
        try { saved = sessionStorage.getItem('data-bs-theme'); } catch (e) {}
        if (saved) {
            document.documentElement.setAttribute('data-bs-theme', saved);
            var icon = document.querySelector('#topbar-theme-btn i');
            if (icon) {
                icon.classList.toggle('bx-moon', saved === 'light');
                icon.classList.toggle('bx-sun', saved === 'dark');
            }
        }

        document.addEventListener('fullscreenchange', function () {
            if (!document.fullscreenElement) document.body.classList.remove('fullscreen-enable');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
</script>
