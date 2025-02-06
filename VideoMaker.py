import cv2
import numpy as np
import pandas as pd
from PIL import Image

class VideoMaker:
    def __init__(self, osd_reader, font_image_path, chroma_key_hex="FF00FF", fps=60.0):
        """
        Removed any references to a hex grid. 
        The 'osd_reader' provides the 'frame_data', and 'font_image_path' is the tile set.
        """
        self.osd_reader = osd_reader
        self.font_image_path = font_image_path
        self.chroma_key_hex = chroma_key_hex
        self.fps = fps

        # Load font image
        self.font_image = self.load_font_image()
        self.tile_cache = {}  # Cache dictionary for pre-blended tiles

        # Set resolution and tile sizes
        self.TILE_WIDTH, self.TILE_HEIGHT, self.RESOLUTION = self.compute_tile_and_resolution()
        self.chroma_key_rgb = self.hex_to_rgb(self.chroma_key_hex)

    def load_font_image(self):
        """Load the font (tile set) image from a file."""
        try:
            return Image.open(self.font_image_path).convert('RGBA')
        except Exception as e:
            raise ValueError(f"Failed to load font image: {e}")

    def compute_tile_and_resolution(self):
        """
        Compute tile dimensions and video resolution based on
        a 4-column x 256-row font image (indices 0..1023).
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

    def hex_to_rgb(self, hex_value):
        """Convert a hex color (e.g. 'FF00FF') to an (R, G, B) tuple."""
        hex_value = hex_value.lstrip('#')
        return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4))

    def get_preblended_tile(self, tile_index):
        """
        Retrieve or cache a pre-blended tile using the numeric tile_index (0..1023).
        We apply the tile's alpha channel over a chroma key background color.
        """
        if tile_index in self.tile_cache:
            return self.tile_cache[tile_index]

        # Determine column and row
        column = tile_index // 256
        row = tile_index % 256

        # If out of range, return a blank tile
        if column > 3 or row > 255:
            blank_tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
            tile_array = np.array(blank_tile)
            blended_tile_bgr = cv2.cvtColor(tile_array[:, :, :3], cv2.COLOR_RGB2BGR)
            self.tile_cache[tile_index] = blended_tile_bgr
            return blended_tile_bgr

        left = int(column * self.TILE_WIDTH)
        upper = int(row * self.TILE_HEIGHT)
        right = int(left + self.TILE_WIDTH)
        lower = int(upper + self.TILE_HEIGHT)

        if right > self.font_image.width or lower > self.font_image.height:
            tile = Image.new('RGBA', (int(self.TILE_WIDTH), int(self.TILE_HEIGHT)), (0, 0, 0, 0))
        else:
            tile = self.font_image.crop((left, upper, right, lower))

        tile_array = np.array(tile)  # RGBA
        if tile_array.shape[2] == 4:
            alpha_channel = tile_array[:, :, 3] / 255.0
            rgb_tile = tile_array[:, :, :3]
        else:
            alpha_channel = np.ones((tile_array.shape[0], tile_array.shape[1]))
            rgb_tile = tile_array

        # Create a background filled with our chroma key color (in RGB)
        blended_tile = np.full(
            (tile_array.shape[0], tile_array.shape[1], 3),
            self.chroma_key_rgb[::-1],  # convert (R,G,B) => (B,G,R) for indexing if needed
            dtype=np.uint8
        )

        # Blend
        for c in range(3):
            blended_tile[:, :, c] = (
                alpha_channel * rgb_tile[:, :, c]
                + (1 - alpha_channel) * blended_tile[:, :, c]
            ).astype(np.uint8)

        # Convert from RGB to BGR for OpenCV
        blended_tile_bgr = cv2.cvtColor(blended_tile.astype('uint8'), cv2.COLOR_RGB2BGR)
        self.tile_cache[tile_index] = blended_tile_bgr
        return blended_tile_bgr

    def render_frame(self, frame_content):
        """
        Render a single frame by placing pre-blended tiles onto a background
        filled with the chroma key color (BGR).
        """
        char_width = self.osd_reader.header["config"]["charWidth"]
        char_height = self.osd_reader.header["config"]["charHeight"]

        # Fill the entire frame with the chroma key color (BGR => reversed)
        frame = np.full((self.RESOLUTION[1], self.RESOLUTION[0], 3),
                        self.chroma_key_rgb[::-1], dtype=np.uint8)

        for i in range(char_height):
            for j in range(char_width):
                idx = i * char_width + j
                if idx < len(frame_content):
                    tile_index = frame_content[idx]
                    tile_bgr = self.get_preblended_tile(tile_index)

                    x = int(j * self.TILE_WIDTH)
                    y = int(i * self.TILE_HEIGHT)
                    th, tw = tile_bgr.shape[:2]

                    frame[y:y + th, x:x + tw] = tile_bgr

        return frame

    def create_video(self, output_path, progress_callback=None):
        """Create the video based on the OSD data."""
        print("Initializing VideoWriter...")
        video = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            self.fps,
            self.RESOLUTION
        )

        if not video.isOpened():
            print("Error: Could not open VideoWriter.")
            return

        blocks = self.osd_reader.frame_data.to_dict(orient="records")
        start_time = blocks[0]['timestamp']
        end_time = blocks[-1]['timestamp']
        num_frames = int((end_time - start_time) * self.fps) + 1
        self.total_frames = num_frames

        print(f"Total frames to render: {num_frames}")

        current_block_index = 0
        for frame_num in range(num_frames):
            current_time = start_time + frame_num / self.fps

            if frame_num % 100 == 0:
                print(f"Processed {frame_num + 1}/{num_frames} frames")

            # Advance block index if needed
            while (
                current_block_index + 1 < len(blocks)
                and current_time >= blocks[current_block_index + 1]['timestamp']
            ):
                current_block_index += 1

            frame_content = blocks[current_block_index]['frameContent']
            frame_bgr = self.render_frame(frame_content)
            video.write(frame_bgr)

            # Optional progress callback
            if progress_callback:
                percentage = (frame_num + 1) / num_frames * 100
                progress_callback(percentage, frame_num)

        video.release()
        print(f"Video created successfully at {output_path}")
