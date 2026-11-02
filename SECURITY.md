# Security policy

Drone Telemetry Studio runs entirely on your machine. Your videos and telemetry files
are never uploaded. The only network traffic is optional OpenStreetMap tile downloads
for the map background, and you can turn those off.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's
[private vulnerability reporting](https://github.com/horakdani/Telemetry_Overlay/security/advisories/new)
instead, with steps to reproduce and the version you tested.

Relevant areas include:

- Crafted SRT or MP4 files that crash the parser or cause unexpected file writes.
- Command or argument injection into the FFmpeg/FFprobe invocations.
- Path handling that could overwrite the source video or files outside the chosen
  output location.

You can expect an initial response within a week.
