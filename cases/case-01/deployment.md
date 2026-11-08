# Scoring service integration note

## Request interface

| Input field | Contents |
|-------------|----------|
| `images` | An array of images to score |

The intake queue assembles uploads in arrival order. One upload can include images
from several capture runs. The service returns one novelty score per image after
processing the upload.

## Capture record

The evaluation archive contains two capture campaigns:

| Campaign | Digit classes recorded |
|----------|------------------------|
| A | 1, 3, 5, 7, 9 |
| B | 0, 2, 4, 6, 8 |

Brightness settings differed between campaigns. The initial and reserve exports
contain distinct images from these campaigns.
