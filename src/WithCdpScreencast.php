<?php

namespace CodingCab\DuskRecordings;

use Facebook\WebDriver\Remote\RemoteWebDriver;

trait WithCdpScreencast
{
    protected array $screencastFrames = [];
    protected bool $isScreencasting = false;
    protected ?string $recordingOutputPath = null;

    public function startScreencast(?string $outputPath = null): void
    {
        $this->recordingOutputPath = $outputPath ?? storage_path('dusk-recordings/' . class_basename($this) . '_' . time() . '.webm');
        $this->screencastFrames = [];
        $this->isScreencasting = true;

        $driver = $this->getScreencastDriver();

        // Enable CDP Page domain and start screencast
        $driver->executeCustomCommand('/session/:sessionId/chromium/send_command_and_get_result', 'POST', [
            'cmd' => 'Page.startScreencast',
            'params' => [
                'format' => 'png',
                'quality' => 80,
                'everyNthFrame' => 1,
            ],
        ]);
    }

    public function captureScreencastFrame(): void
    {
        if (!$this->isScreencasting) {
            return;
        }

        $driver = $this->getScreencastDriver();

        // Take a screenshot and store it
        $screenshot = $driver->takeScreenshot();
        if ($screenshot) {
            $this->screencastFrames[] = [
                'data' => $screenshot,
                'timestamp' => microtime(true),
            ];
        }
    }

    public function stopScreencast(): ?string
    {
        if (!$this->isScreencasting) {
            return null;
        }

        $this->isScreencasting = false;

        $driver = $this->getScreencastDriver();

        try {
            $driver->executeCustomCommand('/session/:sessionId/chromium/send_command_and_get_result', 'POST', [
                'cmd' => 'Page.stopScreencast',
                'params' => [],
            ]);
        } catch (\Exception $e) {
            // Ignore errors when stopping
        }

        if (empty($this->screencastFrames)) {
            return null;
        }

        // Convert frames to video using ffmpeg
        return $this->framesToVideo();
    }

    protected function framesToVideo(): ?string
    {
        if (empty($this->screencastFrames)) {
            return null;
        }

        $tempDir = sys_get_temp_dir() . '/dusk-screencast-' . uniqid();
        mkdir($tempDir, 0755, true);

        // Save frames as images
        foreach ($this->screencastFrames as $index => $frame) {
            $framePath = sprintf('%s/frame_%05d.png', $tempDir, $index);
            file_put_contents($framePath, $frame['data']);
        }

        // Calculate FPS based on frame timestamps
        $frameCount = count($this->screencastFrames);
        if ($frameCount < 2) {
            $this->cleanup($tempDir);
            return null;
        }

        $duration = $this->screencastFrames[$frameCount - 1]['timestamp'] - $this->screencastFrames[0]['timestamp'];
        $fps = $duration > 0 ? round($frameCount / $duration) : 10;
        $fps = max(1, min($fps, 30)); // Clamp between 1 and 30

        // Ensure output directory exists
        $outputDir = dirname($this->recordingOutputPath);
        if (!is_dir($outputDir)) {
            mkdir($outputDir, 0755, true);
        }

        // Use ffmpeg to create video
        $command = sprintf(
            'ffmpeg -y -framerate %d -i %s/frame_%%05d.png -c:v libvpx-vp9 -pix_fmt yuva420p %s 2>/dev/null',
            $fps,
            escapeshellarg($tempDir),
            escapeshellarg($this->recordingOutputPath)
        );

        exec($command, $output, $returnCode);

        $this->cleanup($tempDir);

        return $returnCode === 0 ? $this->recordingOutputPath : null;
    }

    protected function cleanup(string $tempDir): void
    {
        $files = glob($tempDir . '/*');
        foreach ($files as $file) {
            unlink($file);
        }
        rmdir($tempDir);
    }

    abstract protected function getScreencastDriver(): RemoteWebDriver;
}
