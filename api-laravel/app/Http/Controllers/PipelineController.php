<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\Process\Process;

class PipelineController extends Controller
{
    private function lockDir(): string
    {
        return base_path('storage'.DIRECTORY_SEPARATOR.'framework'.DIRECTORY_SEPARATOR.'cache');
    }

    private function lockPath(): string
    {
        return $this->lockDir().DIRECTORY_SEPARATOR.'pipeline_runner.lock';
    }

    private function statePath(): string
    {
        return $this->lockDir().DIRECTORY_SEPARATOR.'pipeline_runner.state.json';
    }

    private function readState(): array
    {
        $statePath = $this->statePath();
        if (! is_file($statePath)) {
            return [];
        }
        try {
            $decoded = json_decode((string) file_get_contents($statePath), true);
            return is_array($decoded) ? $decoded : [];
        } catch (\Throwable $e) {
            return [];
        }
    }

    private function writeState(array $state): void
    {
        $dir = $this->lockDir();
        if (! is_dir($dir)) {
            @mkdir($dir, 0777, true);
        }
        @file_put_contents($this->statePath(), json_encode($state, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    }

    private function readTailLines(string $path, int $maxLines = 200): array
    {
        if (! is_file($path)) {
            return [];
        }
        try {
            $lines = preg_split("/\r\n|\n|\r/", trim((string) file_get_contents($path)));
            if (! is_array($lines)) {
                return [];
            }
            return array_slice($lines, -$maxLines);
        } catch (\Throwable $e) {
            return [];
        }
    }

    public function status(): JsonResponse
    {
        $projectRoot = realpath(base_path('..'));
        $reportPath = ($projectRoot ?: base_path('..')).DIRECTORY_SEPARATOR.'output'.DIRECTORY_SEPARATOR.'pipeline_test_report.txt';

        $state = $this->readState();
        $running = (bool) ($state['running'] ?? false);

        // Best-effort lock probe for current running status.
        $lockPath = $this->lockPath();
        $lockHandle = @fopen($lockPath, 'c+');
        if ($lockHandle) {
            if (@flock($lockHandle, LOCK_EX | LOCK_NB)) {
                @flock($lockHandle, LOCK_UN);
            } else {
                $running = true;
            }
            @fclose($lockHandle);
        }

        return response()->json([
            'running' => $running,
            'started_at' => $state['started_at'] ?? null,
            'finished_at' => $state['finished_at'] ?? null,
            'last_query' => $state['last_query'] ?? null,
            'ok' => $state['ok'] ?? null,
            'rows' => $state['rows'] ?? null,
            'elapsed_ms' => $state['elapsed_ms'] ?? null,
            'report_path' => is_file($reportPath) ? $reportPath : null,
            'output' => $this->readTailLines($reportPath, 200),
        ]);
    }

    public function run(Request $request): JsonResponse
    {
        $data = $request->validate([
            'query' => 'required|string|min:3',
            'concurrency' => 'nullable|integer|min:1|max:8',
            'inactivity' => 'nullable|string|regex:/^\d+[smh]$/',
            'lang' => 'nullable|string|in:th,en',
            'radius' => 'nullable|integer|min:1000|max:50000',
            'depth' => 'nullable|integer|min:1|max:10',
        ]);

        $projectRoot = realpath(base_path('..'));
        if (! $projectRoot) {
            return response()->json([
                'ok' => false,
                'output' => ['Cannot resolve project root'],
            ], 500);
        }

        $queryFile = $projectRoot.DIRECTORY_SEPARATOR.'config'.DIRECTORY_SEPARATOR.'queries.txt';
        $outputCsv = $projectRoot.DIRECTORY_SEPARATOR.'output'.DIRECTORY_SEPARATOR.'results.csv';
        $reportPath = $projectRoot.DIRECTORY_SEPARATOR.'output'.DIRECTORY_SEPARATOR.'pipeline_test_report.txt';

        try {
            if (! is_dir(dirname($queryFile))) {
                mkdir(dirname($queryFile), 0777, true);
            }
            file_put_contents($queryFile, trim($data['query']));
        } catch (\Throwable $e) {
            return response()->json([
                'ok' => false,
                'output' => ['Failed to write query file: '.$e->getMessage()],
            ], 500);
        }

        $lockDir = $this->lockDir();
        if (! is_dir($lockDir)) {
            @mkdir($lockDir, 0777, true);
        }
        $lockPath = $this->lockPath();
        $lockHandle = @fopen($lockPath, 'c+');
        if (! $lockHandle) {
            return response()->json([
                'ok' => false,
                'output' => ['Cannot create pipeline lock file'],
            ], 500);
        }
        if (! @flock($lockHandle, LOCK_EX | LOCK_NB)) {
            @fclose($lockHandle);
            return response()->json([
                'ok' => false,
                'output' => ['Pipeline is already running. Please wait for current run to finish.'],
            ], 429);
        }

        $isWin = strtoupper(substr(PHP_OS, 0, 3)) === 'WIN';
        $configuredPython = env('PIPELINE_PYTHON');
        if ($configuredPython) {
            $cmd = [$configuredPython, 'scripts/run_pipeline_test.py'];
        } elseif ($isWin) {
            // Prefer Python 3.12 on Windows (3.14 has runtime issues with Playwright on some setups)
            $cmd = ['py', '-3.12', 'scripts/run_pipeline_test.py'];
        } else {
            $cmd = ['python3', 'scripts/run_pipeline_test.py'];
        }

        $baseEnv = array_merge($_SERVER ?? [], $_ENV ?? []);
        foreach (['USERPROFILE', 'HOME', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'PATH', 'SYSTEMROOT'] as $key) {
            $val = getenv($key);
            if ($val !== false && $val !== null && $val !== '') {
                $baseEnv[$key] = $val;
            }
        }
        $pipelineApiUrl = env('PIPELINE_INTERNAL_API_URL');
        if (!$pipelineApiUrl && $isWin) {
            // Avoid deadlock when /api/pipeline/run is served by a single-worker dev server.
            $pipelineApiUrl = 'http://127.0.0.1:8010';
        }
        $baseEnv['CHECKIN_API_URL'] = $pipelineApiUrl ?: env('CHECKIN_API_URL', env('APP_URL', 'http://localhost:8000'));
        $baseEnv['PIPELINE_CONCURRENCY'] = (string) ($data['concurrency'] ?? 2);
        $baseEnv['PIPELINE_LANG'] = (string) ($data['lang'] ?? 'th');
        $baseEnv['PIPELINE_INACTIVITY'] = (string) ($data['inactivity'] ?? '3m');
        $baseEnv['PIPELINE_RADIUS'] = (string) ($data['radius'] ?? 7000);
        $baseEnv['PIPELINE_DEPTH'] = (string) ($data['depth'] ?? 2);

        $process = new Process($cmd, $projectRoot, $baseEnv);
        $process->setTimeout(2700);

        $start = microtime(true);
        $output = '';
        $this->writeState([
            'running' => true,
            'started_at' => now()->utc()->toIso8601String(),
            'finished_at' => null,
            'last_query' => trim((string) $data['query']),
            'ok' => null,
            'rows' => null,
            'elapsed_ms' => null,
        ]);
        try {
            $process->run(function ($type, $buffer) use (&$output) {
                $output .= $buffer;
            });
        } catch (\Throwable $e) {
            @flock($lockHandle, LOCK_UN);
            @fclose($lockHandle);
            $this->writeState([
                'running' => false,
                'started_at' => $this->readState()['started_at'] ?? null,
                'finished_at' => now()->utc()->toIso8601String(),
                'last_query' => trim((string) $data['query']),
                'ok' => false,
                'rows' => 0,
                'elapsed_ms' => (int) round((microtime(true) - $start) * 1000),
                'error' => $e->getMessage(),
            ]);
            return response()->json([
                'ok' => false,
                'output' => ['Pipeline run error: '.$e->getMessage()],
            ], 500);
        }
        @flock($lockHandle, LOCK_UN);
        @fclose($lockHandle);
        $elapsedMs = (int) round((microtime(true) - $start) * 1000);

        $rows = 0;
        if (is_file($outputCsv)) {
            try {
                $content = file($outputCsv, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
                $rows = max(0, count($content) - 1);
            } catch (\Throwable $e) {
                $rows = 0;
            }
        }

        $lines = preg_split("/\r\n|\n|\r/", trim($output));
        if (! is_array($lines)) {
            $lines = [];
        }
        $tail = array_slice($lines, -200);

        $this->writeState([
            'running' => false,
            'started_at' => $this->readState()['started_at'] ?? null,
            'finished_at' => now()->utc()->toIso8601String(),
            'last_query' => trim((string) $data['query']),
            'ok' => $process->isSuccessful(),
            'rows' => $rows,
            'elapsed_ms' => $elapsedMs,
        ]);

        return response()->json([
            'ok' => $process->isSuccessful(),
            'elapsed_ms' => $elapsedMs,
            'rows' => $rows,
            'report_path' => is_file($reportPath) ? $reportPath : null,
            'output' => $tail,
        ], $process->isSuccessful() ? 200 : 500);
    }
}

