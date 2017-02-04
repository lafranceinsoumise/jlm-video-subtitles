Those are published caption files downloaded directly from YouTube.


## Structure

A single caption filename follows these semantics:

```
<videoPublicationDate>.<videoTitle>.<captionLang>.<captionId>.vtt
```

where:

- `videoPublicationDate` is in the format `YYYY-MM-DD`, eg: `2017-03-21`.
- `videoTitle` has been stripped of all non-alphanumeric characters.
- `captionLang` is the `ISO 639-1` language code, such as `fr` or `en`.
- `captionId` is YouTube's unique identifier for this caption.

Additionally, captions are sorted into year directories, for clarity.


## How

The `bin/backup.py` script handles downloading these files from YouTube.


## Warning

This is merely a backup for now, there is no point in modifying these files by hand.


## Rationale for WebVTT

[WebVTT](https://w3c.github.io/webvtt/) is a captions format that allows for
comments and many other features. We're using comments to store metadata
about the caption in order to ease synchronization with YouTube.
