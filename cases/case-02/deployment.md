# Scoring service integration note

## Request interface

| Input field | Contents |
|-------------|----------|
| `images` | An array of images from a completed capture session |
| `session_ids` | The capture-session identifier attached to each image |

The capture service closes a session and uploads its images together. The scoring
service then returns one novelty score per image in the upload.

## Capture record

A session identifier is allocated when a capture session starts. Digit classes
are mixed within sessions. Brightness settings are held constant during a session
and varied between sessions.

The initial and reserve exports contain distinct images and distinct capture
sessions. Both exports use the request format above.
