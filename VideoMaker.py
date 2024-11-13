import cv2
import numpy as np
import pandas as pd
from PIL import Image

class VideoMaker:
    def __init__(self, osd_reader, hex_grid_path, font_image_path, chroma_key_hex="FF00FF", fps=60.0):
        self.osd_reader = osd_reader
        self.hex_grid_path = hex_grid_path
        self.font_image_path = font_image_path
        self.chroma_key_hex = chroma_key_hex
        self.fps = fps

        # Load hex grid and font image
        self.hex_grid = self.load_hex_grid()
        self.font_image = self.load_font_image()
        self.tile_cache = {}  # Cache dictionary for pre-blended tiles

        # Set resolution and tile sizes
        self.TILE_WIDTH, self.TILE_HEIGHT, self.RESOLUTION = self.compute_tile_and_resolution()
        self.chroma_key_rgb = self.hex_to_rgb(self.chroma_key_hex)

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
        num_rows = 16*16  # Assuming two columns in the font image
        TILE_HEIGHT = self.font_image.height / num_rows
        TILE_WIDTH = TILE_HEIGHT / 1.5
        grid_width = self.osd_reader.header['config']['charWidth']
        grid_height = self.osd_reader.header['config']['charHeight']
        RESOLUTION = (int(grid_width * TILE_WIDTH), int(grid_height * TILE_HEIGHT))
        return TILE_WIDTH, TILE_HEIGHT, RESOLUTION

    def hex_to_rgb(self, hex_value):
        """Convert a hex color to an RGB tuple."""
        hex_value = hex_value.lstrip('#')
        return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4))

    def get_preblended_tile(self, hex_value):
        """Retrieve or cache a pre-blended tile based on hex value."""
        if hex_value in self.tile_cache:
            return self.tile_cache[hex_value]

        decimal_value = int(hex_value, 16)
        if decimal_value < 256:
            column, row = 0, decimal_value
        else:
            column, row = 1, decimal_value - 256

        left = int(column * self.TILE_WIDTH)
        upper = int(row * self.TILE_HEIGHT)
        right = int(left + self.TILE_WIDTH)
        lower = int(upper + self.TILE_HEIGHT)

        if right > self.font_image.width or lower > self.font_image.height:
            tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
        else:
            tile = self.font_image.crop((left, upper, right, lower))

        tile_array = np.array(tile)
        if tile_array.shape[2] == 4:
            alpha_channel = tile_array[:, :, 3] / 255.0
            rgb_tile = tile_array[:, :, :3]
        else:
            alpha_channel = np.ones((int(self.TILE_HEIGHT), int(self.TILE_WIDTH)))
            rgb_tile = tile_array

        blended_tile = np.full((int(self.TILE_HEIGHT), int(self.TILE_WIDTH), 3), self.chroma_key_rgb[::-1], dtype=np.uint8)
        for c in range(3):
            blended_tile[:, :, c] = (alpha_channel * rgb_tile[:, :, c] + (1 - alpha_channel) * blended_tile[:, :, c]).astype(np.uint8)

        blended_tile_bgr = cv2.cvtColor(blended_tile.astype('uint8'), cv2.COLOR_RGB2BGR)
        self.tile_cache[hex_value] = blended_tile_bgr
        return blended_tile_bgr

    def get_value_from_grid(self, osd_hex_value):
        """Look up the hex grid for the value corresponding to the OSD hex value."""
        try:
            decimal_value = int(osd_hex_value, 16)
            row, col = divmod(decimal_value, 16)
            if 0 <= row < self.hex_grid.shape[0] and 0 <= col < self.hex_grid.shape[1]:
                return self.hex_grid.iat[row, col]
            else:
                return '00'
        except ValueError:
            return '00'

    def render_frame(self, frame_content):
        """Render a frame based on the frame content data."""
        char_width = self.osd_reader.header["config"]["charWidth"]
        char_height = self.osd_reader.header["config"]["charHeight"]
        frame = np.full((self.RESOLUTION[1], self.RESOLUTION[0], 3), self.chroma_key_rgb[::-1], dtype=np.uint8)

        # Convert frame content into a grid and render each tile
        for i in range(char_height):
            for j in range(char_width):
                index = i * char_width + j
                if index < len(frame_content):
                    osd_hex_value = f"{frame_content[index]:02X}"
                    new_hex_value = self.get_value_from_grid(osd_hex_value)
                    tile = self.get_preblended_tile(new_hex_value)
                    x, y = int(j * self.TILE_WIDTH), int(i * self.TILE_HEIGHT)
                    frame[y:y + tile.shape[0], x:x + tile.shape[1]] = tile
        return frame

    def create_video(self, output_path, progress_callback=None):
        """Create the video based on the OSD data."""
        print("Initializing VideoWriter...")
        video = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), self.fps, self.RESOLUTION)

        if not video.isOpened():
            print("Error: Could not open VideoWriter.")
            return

        blocks = self.osd_reader.frame_data.to_dict(orient="records")
        start_time = blocks[0]['timestamp']
        end_time = blocks[-1]['timestamp']
        num_frames = int((end_time - start_time) * self.fps) + 1
        self.total_frames = num_frames  # Store total frames for progress calculation

        print(f"Total frames to render: {num_frames}")

        current_block_index = 0
        for frame_num in range(num_frames):
            current_time = start_time + frame_num / self.fps

            if frame_num % 100 == 0:  # Print every 100 frames
                print(f"Processed {frame_num + 1}/{num_frames} frames")

            while (current_block_index + 1 < len(blocks) and current_time >= blocks[current_block_index + 1][
                'timestamp']):
                current_block_index += 1

            frame_content = blocks[current_block_index]['frameContent']
            frame = self.render_frame(frame_content)
            video.write(frame)

            # Update progress bar and remaining time every 100 frames
            if progress_callback:
                percentage = (frame_num + 1) / num_frames * 100
                progress_callback(percentage, frame_num)  # Pass both percentage and frame_num

        video.release()
        print(f"Video created successfully at {output_path}")
