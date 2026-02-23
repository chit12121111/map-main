<?php

namespace App\Http\Controllers;

use App\Models\PipelineRun;
use App\Models\PipelineRunLog;
use App\Models\UiPreference;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\Process\Process;

class PipelineController extends Controller
{
    private const STATUS_RUNNING = 'RUNNING';
    private const STATUS_SUCCESS = 'SUCCESS';
    private const STATUS_FAILED = 'FAILED';
    private const STATUS_IDLE = 'IDLE';

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

    private function appendRunLogs(int $runId, array $lines, int &$seq): void
    {
        if (empty($lines)) {
            return;
        }

        $rows = [];
        $now = now();
        foreach ($lines as $line) {
            if (! is_string($line)) {
                continue;
            }
            $trimmed = trim($line);
            if ($trimmed === '') {
                continue;
            }
            $rows[] = [
                'pipeline_run_id' => $runId,
                'seq' => $seq++,
                'level' => 'info',
                'line' => $trimmed,
                'created_at' => $now,
                'updated_at' => $now,
            ];
        }

        if (! empty($rows)) {
            PipelineRunLog::query()->insert($rows);
        }
    }

    private function formatRun(PipelineRun $run): array
    {
        return [
            'id' => $run->id,
            'query' => $run->query,
            'status' => $run->status,
            'running' => $run->status === self::STATUS_RUNNING,
            'started_at' => $run->started_at?->utc()->toIso8601String(),
            'finished_at' => $run->finished_at?->utc()->toIso8601String(),
            'elapsed_ms' => $run->elapsed_ms,
            'rows' => $run->rows,
            'report_path' => $run->report_path,
            'error' => $run->error,
            'created_at' => $run->created_at?->utc()->toIso8601String(),
            'updated_at' => $run->updated_at?->utc()->toIso8601String(),
        ];
    }

    private function pruneOldRuns(): void
    {
        $days = (int) env('PIPELINE_RUN_RETENTION_DAYS', 30);
        if ($days <= 0) {
            return;
        }
        $cutoff = now()->subDays($days);
        PipelineRun::query()->where('created_at', '<', $cutoff)->delete();
    }

    public function status(): JsonResponse
    {
        $projectRoot = realpath(base_path('..'));
        $reportPath = ($projectRoot ?: base_path('..')).DIRECTORY_SEPARATOR.'output'.DIRECTORY_SEPARATOR.'pipeline_test_report.txt';

        $state = $this->readState();
        $running = (bool) ($state['running'] ?? false);
        $runId = isset($state['run_id']) ? (int) $state['run_id'] : null;
        $latestRun = $runId ? PipelineRun::query()->find($runId) : PipelineRun::query()->latest('id')->first();

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

        if ($latestRun) {
            $running = $running || $latestRun->status === self::STATUS_RUNNING;
        }

        $output = [];
        if ($latestRun) {
            $output = PipelineRunLog::query()
                ->where('pipeline_run_id', $latestRun->id)
                ->orderByDesc('seq')
                ->limit(200)
                ->pluck('line')
                ->reverse()
                ->values()
                ->all();
        }
        if (empty($output) && is_file($reportPath)) {
            $output = $this->readTailLines($reportPath, 200);
        }

        return response()->json([
            'run_id' => $latestRun?->id,
            'running' => $running,
            'status' => $latestRun?->status ?? ($running ? self::STATUS_RUNNING : self::STATUS_IDLE),
            'started_at' => $latestRun?->started_at?->utc()->toIso8601String() ?? ($state['started_at'] ?? null),
            'finished_at' => $latestRun?->finished_at?->utc()->toIso8601String() ?? ($state['finished_at'] ?? null),
            'last_query' => $latestRun?->query ?? ($state['last_query'] ?? null),
            'ok' => $latestRun ? ($latestRun->status === self::STATUS_SUCCESS) : ($state['ok'] ?? null),
            'rows' => $latestRun?->rows ?? ($state['rows'] ?? null),
            'elapsed_ms' => $latestRun?->elapsed_ms ?? ($state['elapsed_ms'] ?? null),
            'error' => $latestRun?->error,
            'report_path' => is_file($reportPath) ? $reportPath : null,
            'output' => $output,
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
            'depth' => 'nullable|integer|min:1|max:100',
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
        $run = PipelineRun::query()->create([
            'query' => trim((string) $data['query']),
            'status' => self::STATUS_RUNNING,
            'started_at' => now()->utc(),
            'source' => 'logs_console',
        ]);
        $seq = 1;
        $buffer = '';
        $this->writeState([
            'running' => true,
            'run_id' => $run->id,
            'started_at' => now()->utc()->toIso8601String(),
            'finished_at' => null,
            'last_query' => trim((string) $data['query']),
            'ok' => null,
            'rows' => null,
            'elapsed_ms' => null,
        ]);
        try {
            $process->run(function ($type, $chunk) use (&$output, $run, &$seq, &$buffer) {
                $output .= $chunk;
                $buffer .= $chunk;
                $parts = preg_split("/\r\n|\n|\r/", $buffer);
                if (! is_array($parts) || empty($parts)) {
                    return;
                }
                $buffer = (string) array_pop($parts);
                $this->appendRunLogs((int) $run->id, $parts, $seq);
            });
            if (trim($buffer) !== '') {
                $this->appendRunLogs((int) $run->id, [$buffer], $seq);
            }
        } catch (\Throwable $e) {
            @flock($lockHandle, LOCK_UN);
            @fclose($lockHandle);
            $run->update([
                'status' => self::STATUS_FAILED,
                'finished_at' => now()->utc(),
                'elapsed_ms' => (int) round((microtime(true) - $start) * 1000),
                'rows' => 0,
                'error' => $e->getMessage(),
                'report_path' => is_file($reportPath) ? $reportPath : null,
            ]);
            $this->writeState([
                'running' => false,
                'run_id' => $run->id,
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
                'run_id' => $run->id,
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
            'run_id' => $run->id,
            'started_at' => $this->readState()['started_at'] ?? null,
            'finished_at' => now()->utc()->toIso8601String(),
            'last_query' => trim((string) $data['query']),
            'ok' => $process->isSuccessful(),
            'rows' => $rows,
            'elapsed_ms' => $elapsedMs,
        ]);
        $run->update([
            'status' => $process->isSuccessful() ? self::STATUS_SUCCESS : self::STATUS_FAILED,
            'finished_at' => now()->utc(),
            'elapsed_ms' => $elapsedMs,
            'rows' => $rows,
            'report_path' => is_file($reportPath) ? $reportPath : null,
            'error' => $process->isSuccessful() ? null : implode("\n", array_slice($tail, -10)),
        ]);
        $this->pruneOldRuns();

        return response()->json([
            'ok' => $process->isSuccessful(),
            'run_id' => $run->id,
            'elapsed_ms' => $elapsedMs,
            'rows' => $rows,
            'report_path' => is_file($reportPath) ? $reportPath : null,
            'output' => $tail,
        ], $process->isSuccessful() ? 200 : 500);
    }

    public function runs(Request $request): JsonResponse
    {
        $limit = (int) $request->get('limit', 50);
        $runs = PipelineRun::query()
            ->orderByDesc('id')
            ->limit(max(1, min(200, $limit)))
            ->get();

        return response()->json([
            'total' => $runs->count(),
            'runs' => $runs->map(fn (PipelineRun $run) => $this->formatRun($run))->values(),
        ]);
    }

    public function runDetail(string $id): JsonResponse
    {
        $run = PipelineRun::query()->findOrFail((int) $id);

        return response()->json($this->formatRun($run));
    }

    public function runLogs(string $id, Request $request): JsonResponse
    {
        $runId = (int) $id;
        $sinceSeq = (int) $request->get('since_seq', 0);
        $limit = max(1, min(1000, (int) $request->get('limit', 500)));
        $query = PipelineRunLog::query()
            ->where('pipeline_run_id', $runId)
            ->orderBy('seq')
            ->limit($limit);
        if ($sinceSeq > 0) {
            $query->where('seq', '>', $sinceSeq);
        }
        $logs = $query->get(['seq', 'level', 'line', 'created_at']);

        return response()->json([
            'run_id' => $runId,
            'count' => $logs->count(),
            'logs' => $logs->map(fn (PipelineRunLog $log) => [
                'seq' => $log->seq,
                'level' => $log->level,
                'line' => $log->line,
                'created_at' => $log->created_at?->utc()->toIso8601String(),
            ])->values(),
            'last_seq' => $logs->last()?->seq ?? $sinceSeq,
        ]);
    }

    public function getPreference(string $key, Request $request): JsonResponse
    {
        $scope = (string) $request->get('scope', 'global');
        $pref = UiPreference::query()
            ->where('pref_key', $key)
            ->where('scope', $scope)
            ->first();

        return response()->json([
            'key' => $key,
            'scope' => $scope,
            'value' => $pref?->value ?? null,
        ]);
    }

    public function putPreference(string $key, Request $request): JsonResponse
    {
        $data = $request->validate([
            'scope' => 'nullable|string|max:50',
            'value' => 'required|array',
        ]);
        $scope = (string) ($data['scope'] ?? 'global');
        $pref = UiPreference::query()->updateOrCreate(
            ['pref_key' => $key, 'scope' => $scope],
            ['value' => $data['value']]
        );

        return response()->json([
            'key' => $pref->pref_key,
            'scope' => $pref->scope,
            'value' => $pref->value,
        ]);
    }
}

