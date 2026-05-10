<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\App;
use Illuminate\Support\Facades\Session;

class HomeController extends Controller
{
    /**
     * Create a new controller instance.
     *
     * @return void
     */
    public function __construct()
    {
        $this->middleware('auth');
    }

    /**
     * Show the application dashboard.
     *
     * @return \Illuminate\Contracts\Support\Renderable
     */
    public function index(Request $request)
    {
        if (view()->exists($request->path())) {
            return view($request->path());
        }
        return abort(404);
    }

    public function root()
    {
        return view('index');
    }

    /*Language Translation*/
    public function lang($locale)
    {
        $available = config('app.available_locales', ['en']);
        if (!in_array($locale, $available, true)) {
            return redirect()->back();
        }
        App::setLocale($locale);
        Session::put('lang', $locale);
        Session::save();
        cookie()->queue('lang', $locale, 60 * 24 * 365);
        return redirect()->back()->with('locale', $locale);
    }
}
