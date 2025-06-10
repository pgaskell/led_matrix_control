#!/usr/bin/env python3
import sys
import os
from PIL import Image, ImageSequence

def resize_image(input_path, output_path, size):
    img = Image.open(input_path)
    # Check if it's an animated image (GIF)
    if getattr(img, "is_animated", False):
        frames = []
        duration = img.info.get("duration", 100)
        loop = img.info.get("loop", 0)
        for frame in ImageSequence.Iterator(img):
            frame = frame.convert("RGBA")
            resized = frame.resize((size, size), Image.LANCZOS)
            frames.append(resized)
        # Save the animation
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            loop=loop,
            duration=duration,
            disposal=2,
            transparency=img.info.get("transparency", 255)
        )
    else:
        # Static image (e.g., PNG)
        img = img.convert("RGBA")
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(output_path)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Resize animated GIFs or PNGs to 24x24 or 16x16."
    )
    parser.add_argument(
        "input",
        help="Path to input file (GIF or PNG)."
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Path to output file. If omitted, adds suffix based on size."
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        choices=[16, 24],
        default=24,
        help="Target size (default: 24)."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    input_path = args.input
    size = args.size
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_{size}x{size}{ext}"
    resize_image(input_path, output_path, size)
    print(f"Saved resized image to {output_path}")

if __name__ == "__main__":
    main()
