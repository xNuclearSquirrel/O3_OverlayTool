import numpy as np
import pandas as pd
from PIL import Image
import subprocess


class TransparentVideoMaker:
    def __init__(self, osd_reader, hex_grid_path, font_image_path, fps=60.0):
        self.osd_reader = osd_reader
        self.hex_grid_path = hex_grid_path
        self.font_image_path = font_image_path
        self.fps = fps

        # Load hex grid and font image
        self.hex_grid = self.load_hex_grid()
        self.font_image = self.load_font_image()
        self.tile_cache = {}  # Cache dictionary for pre-rendered tiles to improve performance

        # Set resolution and tile sizes
        self.TILE_WIDTH, self.TILE_HEIGHT, self.RESOLUTION = self.compute_tile_and_resolution()

    def load_hex_grid(self):
        """Load the hex grid from a CSV file."""
        try:
            return pd.read_csv(self.hex_grid_path, header=None)
        except Exception as e:
            raise ValueError(f"Failed to load hex grid CSV: {e}")

    def load_font_image(self):
        """Load the font image from a file."""
        try:
            return Image.open(self.font_image_path).convert('RGBA')
        except Exception as e:
            raise ValueError(f"Failed to load font image: {e}")

    def compute_tile_and_resolution(self):
        """Compute tile dimensions and video resolution based on font image and OSD configuration."""
        num_rows = 16 * 16  # Assuming two columns in the font image
        TILE_HEIGHT = self.font_image.height / num_rows
        TILE_WIDTH = TILE_HEIGHT / 1.5
        grid_width = self.osd_reader.header['config']['charWidth']
        grid_height = self.osd_reader.header['config']['charHeight']
        RESOLUTION = (int(grid_width * TILE_WIDTH), int(grid_height * TILE_HEIGHT))
        return TILE_WIDTH, TILE_HEIGHT, RESOLUTION

    def get_tile_with_alpha(self, hex_value):
        """Retrieve or cache a tile with transparency based on the hex value."""
        if hex_value in self.tile_cache:
            return self.tile_cache[hex_value]

        decimal_value = int(hex_value, 16)
        column, row = (0, decimal_value) if decimal_value < 256 else (1, decimal_value - 256)

        left = int(column * self.TILE_WIDTH)
        upper = int(row * self.TILE_HEIGHT)
        right = int(left + self.TILE_WIDTH)
        lower = int(upper + self.TILE_HEIGHT)

        # Crop tile from font image, default to transparent if out of bounds
        if right > self.font_image.width or lower > self.font_image.height:
            tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
        else:
            tile = self.font_image.crop((left, upper, right, lower))

        # Cache the tile as an RGBA array and return it
        tile_array = np.array(tile)
        self.tile_cache[hex_value] = tile_array
        return tile_array

    def get_value_from_grid(self, osd_value):
        """Look up the hex grid for the value corresponding to the OSD integer value."""
        try:
            # Compute row and column directly from the decimal value
            row, col = divmod(osd_value, 16)
            if 0 <= row < self.hex_grid.shape[0] and 0 <= col < self.hex_grid.shape[1]:
                return self.hex_grid.iat[row, col]
            else:
                return '00'
        except (ValueError, TypeError):
            return '00'

    def render_frame_with_alpha(self, frame_content):
        """Render a frame with alpha channel based on the frame content data."""
        char_width = self.osd_reader.header["config"]["charWidth"]
        char_height = self.osd_reader.header["config"]["charHeight"]
        frame = np.zeros((self.RESOLUTION[1], self.RESOLUTION[0], 4), dtype=np.uint8)  # RGBA frame

        # Convert frame content into a grid and render each tile
        for i in range(char_height):
            for j in range(char_width):
                index = i * char_width + j
                if index < len(frame_content):
                    osd_value = frame_content[index]
                    new_value = self.get_value_from_grid(osd_value) 
                    tile = self.get_tile_with_alpha(new_value)
                    x, y = int(j * self.TILE_WIDTH), int(i * self.TILE_HEIGHT)

                    # Place the tile onto the frame, preserving transparency
                    frame[y:y + tile.shape[0], x:x + tile.shape[1], :] = tile
        return frame

    def create_video(self, output_path, progress_callback=None):
        """Main method to create the video using FFmpeg piping for improved performance."""
        # Start the FFmpeg process with a pipe for input
        ffmpeg_command = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{self.RESOLUTION[0]}x{self.RESOLUTION[1]}",
            "-r", str(self.fps),
            "-i", "-",  # Read from stdin
            "-c:v", "qtrle",  # Codec for MOV with alpha
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

            # Update block index based on timestamp
            while (current_block_index + 1 < len(blocks) and current_time >= blocks[current_block_index + 1][
                'timestamp']):
                current_block_index += 1

            if frame_num % 100 == 0:  # Print every 100 frames
                print(f"Processed {frame_num + 1}/{num_frames} frames")

            frame_content = blocks[current_block_index]['frameContent']
            frame = self.render_frame_with_alpha(frame_content)

            # Write the frame directly to FFmpeg via stdin
            process.stdin.write(frame.tobytes())

            # Update progress every 100 frames if a callback is provided
            if progress_callback:
                percentage = (frame_num + 1) / num_frames * 100
                progress_callback(percentage, frame_num)
                #print(f"Processed {frame_num + 1}/{num_frames} frames")

        process.stdin.close()
        process.wait()
        print(f"Video created successfully at {output_path}")
