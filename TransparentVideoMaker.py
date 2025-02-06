import numpy as np
import pandas as pd
from PIL import Image
import subprocess


class TransparentVideoMaker:
    def __init__(self, osd_reader, font_image_path, fps=60.0):
        """
        Removed any references to a hex grid. 
        The 'osd_reader' provides the 'frame_data', and 'font_image_path' is the tile set.
        """
        self.osd_reader = osd_reader
        self.font_image_path = font_image_path
        self.fps = fps

        # Load font image
        self.font_image = self.load_font_image()
        self.tile_cache = {}  # Cache dictionary for pre-rendered tiles to improve performance

        # Set resolution and tile sizes
        self.TILE_WIDTH, self.TILE_HEIGHT, self.RESOLUTION = self.compute_tile_and_resolution()

    def load_font_image(self):
        """Load the font (tile set) image from a file."""
        try:
            return Image.open(self.font_image_path).convert('RGBA')
        except Exception as e:
            raise ValueError(f"Failed to load font image: {e}")

    def compute_tile_and_resolution(self):
        """
        Compute tile dimensions and video resolution based on the assumption
        of 256 rows (tile indices 0..255 per column) and up to 4 columns (0..3).
        So we can handle tile indices 0..1023 if needed.

        font_image layout:
         - total columns = 4
         - total rows    = 256
         => each tile width  = font_image.width / 4
         => each tile height = font_image.height / 256

        Then we scale the final resolution by the OSD config (charWidth x charHeight).
        """
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
        """
        Retrieve or cache a tile (with RGBA) based on a numeric tile_index.
        We assume tile_index is an integer 0..1023 max.
        """
        if tile_index in self.tile_cache:
            return self.tile_cache[tile_index]

        # Determine column and row based on tile_index
        column = tile_index // 256  # 0..3
        row = tile_index % 256  # 0..255

        # If out of range, return a fully transparent tile
        if column > 3 or row > 255:
            blank_tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
            tile_array = np.array(blank_tile)
            self.tile_cache[tile_index] = tile_array
            return tile_array

        left = int(column * self.TILE_WIDTH)
        upper = int(row * self.TILE_HEIGHT)
        right = int(left + self.TILE_WIDTH)
        lower = int(upper + self.TILE_HEIGHT)

        # Crop the tile; if out of bounds, make it transparent
        if right > self.font_image.width or lower > self.font_image.height:
            tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
        else:
            tile = self.font_image.crop((left, upper, right, lower))

        tile_array = np.array(tile)
        self.tile_cache[tile_index] = tile_array
        return tile_array

    def render_frame_with_alpha(self, frame_content):
        """
        Render a frame with alpha channel, placing tiles onto an RGBA frame.
        The OSD data in 'frame_content' is a list of integer indices referencing the tiles.
        """
        char_width = self.osd_reader.header["config"]["charWidth"]
        char_height = self.osd_reader.header["config"]["charHeight"]
        frame = np.zeros((self.RESOLUTION[1], self.RESOLUTION[0], 4), dtype=np.uint8)  # RGBA frame (transparent)

        for i in range(char_height):
            for j in range(char_width):
                index = i * char_width + j
                if index < len(frame_content):
                    tile_index = frame_content[index]
                    tile = self.get_tile_with_alpha(tile_index)

                    # Calculate position for this tile
                    x = int(j * self.TILE_WIDTH)
                    y = int(i * self.TILE_HEIGHT)

                    tile_h, tile_w = tile.shape[:2]
                    frame[y:y + tile_h, x:x + tile_w, :] = tile

        return frame

    def create_video(self, output_path, progress_callback=None):
        """
        Create a transparent video by piping raw RGBA frames into FFmpeg using 'qtrle' codec for alpha.
        """
        ffmpeg_command = [
            "ffmpeg",
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

            # Pick the correct OSD frame block based on timestamp
            while (
                    current_block_index + 1 < len(blocks)
                    and current_time >= blocks[current_block_index + 1]['timestamp']
            ):
                current_block_index += 1

            if frame_num % 100 == 0:
                print(f"Processed {frame_num + 1}/{num_frames} frames")

            frame_content = blocks[current_block_index]['frameContent']
            frame = self.render_frame_with_alpha(frame_content)

            # Send to FFmpeg
            process.stdin.write(frame.tobytes())

            # Optional progress callback
            if progress_callback:
                percentage = (frame_num + 1) / num_frames * 100
                progress_callback(percentage, frame_num)

        process.stdin.close()
        process.wait()
        print(f"Video created successfully at {output_path}")
