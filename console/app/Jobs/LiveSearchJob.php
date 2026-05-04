<?php

namespace App\Jobs;

class LiveSearchJob extends RunPartsWatchJob
{
    /**
     * @param string[] $catalogKeys catalog_keys to scope the search to (passed as repeated --bike).
     */
    public function __construct(int $syncRunId, public string $query, public array $catalogKeys = [])
    {
        parent::__construct($syncRunId);
    }

    protected function arguments(): array
    {
        $args = ['search', '--query', $this->query];
        foreach ($this->catalogKeys as $key) {
            $args[] = '--bike-key';
            $args[] = $key;
        }
        return $args;
    }
}
