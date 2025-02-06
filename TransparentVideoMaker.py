import os, sys
import numpy as np
import pandas as pd
from PIL import Image
import subprocess

def resource_path(relative_path):
    """
    PyInstaller helper: gets the absolute path of a bundled file.
    If running from source, it uses this file's directory;
    if running from .exe, it uses the _MEIPASS temp folder.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

class TransparentVideoMaker:
    def __init__(self, osd_reader, font_image_path, fps=60.0):
        self.osd_reader = osd_reader
        self.font_image_path = font_image_path
        self.fps = fps

        # Load font image
        self.font_image = self.load_font_image()
        self.tile_cache = {}

        # Set resolution and tile sizes
        self.TILE_WIDTH, self.TILE_HEIGHT, self.RESOLUTION = self.compute_tile_and_resolution()

    def load_font_image(self):
        try:
            return Image.open(self.font_image_path).convert('RGBA')
        except Exception as e:
            raise ValueError(f"Failed to load font image: {e}")

    def compute_tile_and_resolution(self):
        num_columns = 4
        num_rows = 256
        tile_width = self.font_image.width / num_columns
        tile_height = self.font_image.height / num_rows

        grid_width = self.osd_reader.header['config']['charWidth']
        grid_height = self.osd_reader.header['config']['charHeight']
        resolution = (
            int(grid_width * tile_width),
            int(grid_height * tile_height)
        )
        return tile_width, tile_height, resolution

    def get_tile_with_alpha(self, tile_index):
        if tile_index in self.tile_cache:
            return self.tile_cache[tile_index]

        column = tile_index // 256
        row = tile_index % 256

        if column > 3 or row > 255:
            blank_tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
            tile_array = np.array(blank_tile)
            self.tile_cache[tile_index] = tile_array
            return tile_array

        left = int(column * self.TILE_WIDTH)
        upper = int(row * self.TILE_HEIGHT)
        right = int(left + self.TILE_WIDTH)
        lower = int(upper + self.TILE_HEIGHT)

        if right > self.font_image.width or lower > self.font_image.height:
            tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
        else:
            tile = self.font_image.crop((left, upper, right, lower))

        tile_array = np.array(tile)
        self.tile_cache[tile_index] = tile_array
        return tile_array

    def render_frame_with_alpha(self, frame_content):
        char_width = self.osd_reader.header["config"]["charWidth"]
        char_height = self.osd_reader.header["config"]["charHeight"]
        frame = np.zeros((self.RESOLUTION[1], self.RESOLUTION[0], 4), dtype=np.uint8)

        for i in range(char_height):
            for j in range(char_width):
                idx = i * char_width + j
                if idx < len(frame_content):
                    tile_index = frame_content[idx]
                    tile = self.get_tile_with_alpha(tile_index)

                    x = int(j * self.TILE_WIDTH)
                    y = int(i * self.TILE_HEIGHT)
                    tile_h, tile_w = tile.shape[:2]
                    frame[y:y + tile_h, x:x + tile_w, :] = tile

        return frame

    def create_video(self, output_path, progress_callback=None):
        # 1) Get the local path to ffmpeg.exe
        ffmpeg_path = resource_path(r"ffmpeg\bin\ffmpeg.exe")

        # 2) Build the command with ffmpeg_path at the start
        ffmpeg_command = [
            ffmpeg_path,        # <-- must be first item to actually call ffmpeg.exe
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{self.RESOLUTION[0]}x{self.RESOLUTION[1]}",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "qtrle",
            "-pix_fmt", "rgba",
            output_path
        ]

        process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

        blocks = self.osd_reader.frame_data.to_dict(orient="records")
        start_time = blocks[0]['timestamp']
        end_time = blocks[-1]['timestamp']
        num_frames = int((end_time - start_time) * self.fps) + 1
        self.total_frames = num_frames

        print(f"Total frames to render: {num_frames}")

        current_block_index = 0
        for frame_num in range(num_frames):
            current_time = start_time + frame_num / self.fps

            while (current_block_index + 1 < len(blocks) and
                   current_time >= blocks[current_block_index + 1]['timestamp']):
                current_block_index += 1

            if frame_num % 100 == 0:
                print(f"Processed {frame_num + 1}/{num_frames} frames")

            frame_content = blocks[current_block_index]['frameContent']
            frame = self.render_frame_with_alpha(frame_content)
            process.stdin.write(frame.tobytes())

            if progress_callback:
                percentage = (frame_num + 1) / num_frames * 100
                progress_callback(percentage, frame_num)

        process.stdin.close()
        process.wait()
        print(f"Video created successfully at {output_path}")
