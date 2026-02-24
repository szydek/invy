#!/usr/bin/env python3
from pathlib import Path
import argparse

AUDIO_EXTS = {".m4a", ".mp3", ".flac", ".wav", ".aiff", ".aif"}

def is_audio(p: Path):
    return p.is_file() and p.suffix.lower() in AUDIO_EXTS

def main():
    ap = argparse.ArgumentParser(description="Mirror Apple Music library into Invy static/audio using symlinks.")
    ap.add_argument(
        "--music-root",
        default=str(Path("~/Music/Music/Media.localized/Music").expanduser()),
        help="Apple Music root folder"
    )
    ap.add_argument(
        "--out-dir",
        default=str(Path("~/GitHub/invy/static/audio").expanduser()),
        help="Invy static audio directory"
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing symlinks")
    ap.add_argument("--dry-run", action="store_true", help="Preview actions without writing")

    args = ap.parse_args()

    music_root = Path(args.music_root).expanduser()
    out_dir = Path(args.out_dir).expanduser()

    if not music_root.exists():
        print(f"Music root not found: {music_root}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    linked = 0
    skipped = 0

    for artist_dir in music_root.iterdir():
        if not artist_dir.is_dir():
            continue

        for album_dir in artist_dir.iterdir():
            if not album_dir.is_dir():
                continue

            for track in album_dir.iterdir():
                if not is_audio(track):
                    continue

                dest_dir = out_dir / artist_dir.name / album_dir.name
                dest_dir.mkdir(parents=True, exist_ok=True)

                link_path = dest_dir / track.name

                if args.dry_run:
                    print(f"LINK {track} -> {link_path}")
                    linked += 1
                    continue

                if link_path.exists():
                    if args.force:
                        link_path.unlink()
                    else:
                        skipped += 1
                        continue

                link_path.symlink_to(track)
                print(f"Linked: {track.name}")
                linked += 1

    print(f"\nDone. Linked: {linked}  Skipped: {skipped}")
    print(f"Output directory: {out_dir}")

if __name__ == "__main__":
    main()