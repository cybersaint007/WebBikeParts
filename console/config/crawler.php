<?php

return [
    'bin' => env('WATCHER_PARTS_WATCH_BIN', '/usr/local/bin/parts-watch'),
    'cwd' => env('WATCHER_PARTS_WATCH_CWD', base_path('..')),
];
