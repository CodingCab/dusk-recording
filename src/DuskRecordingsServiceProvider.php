<?php


namespace CodingCab\DuskRecordings;


use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\View;
use Illuminate\Support\ServiceProvider as BaseServiceProvider;

class DuskRecordingsServiceProvider extends BaseServiceProvider
{

    public function boot()
    {
        $this->loadViewsFrom(__DIR__ . '/views', 'screenrecording');

        $this->publishes([
            __DIR__ . '/config/dusk-recordings.php' => config_path('dusk-recordings.php')
        ]);

        if(!$this->app->environment('production')) {
            Route::group([
                'prefix' => '_screenrecording',
                'domain' => null,
            ], function() {
                Route::get('/bootstrap', function () {
                    return View::make('screenrecording::bootstrap');
                });
            });
        }

        if ($this->app->runningInConsole()) {
            $this->commands([
                Console\InstallCommand::class
            ]);
        }
    }

    public function register()
    {
        $this->mergeConfigFrom(
            __DIR__.'/config/dusk-recordings.php', 'dusk-recordings'
        );
    }
}
