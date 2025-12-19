<?php

namespace CodingCab\DuskRecordings;

trait WithScreenshotRecording
{
    protected array $recordingFrames = [];
    protected bool $isRecording = false;
    protected ?string $recordingPath = null;
    protected int $frameInterval = 100; // ms between frames

    public function startRecording(?string $filename = null): void
    {
        $this->recordingFrames = [];
        $this->isRecording = true;

        $filename = $filename ?? class_basename($this) . '_' . $this->name() . '_' . time();
        $this->recordingPath = $this->getRecordingDirectory() . '/' . $filename . '.webm';
    }

    public function captureFrame(): void
    {
        if (!$this->isRecording) {
            return;
        }

        try {
            $screenshot = $this->browser()->driver->takeScreenshot();
            if ($screenshot) {
                $this->recordingFrames[] = [
                    'data' => $screenshot,
                    'timestamp' => microtime(true),
                ];
            }
        } catch (\Exception $e) {
            // Ignore capture errors
        }
    }

    public function stopRecording(): ?string
    {
        if (!$this->isRecording) {
            return null;
        }

        $this->isRecording = false;

        if (count($this->recordingFrames) < 2) {
            return null;
        }

        return $this->createVideoFromFrames();
    }

    protected function createVideoFromFrames(): ?string
    {
        $tempDir = sys_get_temp_dir() . '/dusk-recording-' . uniqid();
        mkdir($tempDir, 0755, true);

        // Save frames as PNG images
        foreach ($this->recordingFrames as $index => $frame) {
            $framePath = sprintf('%s/frame_%06d.png', $tempDir, $index);
            file_put_contents($framePath, $frame['data']);
        }

        // Calculate actual FPS from timestamps
        $frameCount = count($this->recordingFrames);
        $firstTimestamp = $this->recordingFrames[0]['timestamp'];
        $lastTimestamp = $this->recordingFrames[$frameCount - 1]['timestamp'];
        $duration = $lastTimestamp - $firstTimestamp;

        $fps = $duration > 0 ? round($frameCount / $duration) : 10;
        $fps = max(1, min($fps, 30));

        // Ensure output directory exists
        $outputDir = dirname($this->recordingPath);
        if (!is_dir($outputDir)) {
            mkdir($outputDir, 0755, true);
        }

        // Create video with ffmpeg
        $command = sprintf(
            'ffmpeg -y -framerate %d -i "%s/frame_%%06d.png" -c:v libvpx-vp9 -b:v 1M -pix_fmt yuv420p "%s" 2>&1',
            $fps,
            $tempDir,
            $this->recordingPath
        );

        exec($command, $output, $returnCode);

        // Cleanup temp files
        array_map('unlink', glob($tempDir . '/*.png'));
        rmdir($tempDir);

        if ($returnCode !== 0) {
            return null;
        }

        $this->recordingFrames = [];
        return $this->recordingPath;
    }

    protected function getRecordingDirectory(): string
    {
        $dir = config('dusk-recordings.target_directory', base_path('tests/Browser/recordings'));

        if (!is_dir($dir)) {
            mkdir($dir, 0755, true);
        }

        return $dir;
    }

    public function recordWhile(callable $callback): ?string
    {
        $this->startRecording();

        // Capture frames during the callback
        $captureCallback = function () {
            while ($this->isRecording) {
                $this->captureFrame();
                usleep($this->frameInterval * 1000);
            }
        };

        // Run capture in parallel would be ideal, but for simplicity
        // we'll capture before and after each action
        try {
            $this->captureFrame();
            $callback();
            $this->captureFrame();
        } finally {
            return $this->stopRecording();
        }
    }
}
