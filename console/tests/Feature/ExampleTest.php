<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ExampleTest extends TestCase
{
    /**
     * A basic test example.
     *
     * @return void
     */
    public function test_example()
    {
        // Root redirects to /login for unauthenticated users
        $response = $this->get('/');
        $response->assertRedirect('/login');

        // Login page itself is publicly accessible
        $this->get('/login')->assertStatus(200);
    }
}
