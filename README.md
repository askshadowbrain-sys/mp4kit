# mp4kit

A small MP4 reader and writer in plain Python (3.10+, standard library only), built one step per episode
in the tutorial series **MP4 from Scratch** on The Shadow Brains YouTube channel.

By the end of the series it can:

- `mp4kit dump`: print any MP4's box tree (season 1)
- `mp4kit frame`: find and extract any frame by its time (season 2)
- `mp4kit mux`: write a playable MP4 from an H.264 stream and an AAC stream (season 3)
- `mp4kit frag`: write fragmented MP4, read HEVC, AV1, HDR and encrypted files, and diagnose broken ones (season 4)

Each episode adds one tagged step (`ep01` … `ep36`). Check out a tag to see the code exactly as it was at
the end of that episode:

```
git checkout ep06
```

Status: the series is in production. Episode links will be added here as episodes are published.

## License

MIT. See [LICENSE](LICENSE).
