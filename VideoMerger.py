
from moviepy import VideoFileClip, CompositeVideoClip

class VideoMerger:
    def merge_overlay(self,input_path,output_path,final_path,progress_callback=None):
        video_clip = VideoFileClip((input_path)) 
        overlay_clip = VideoFileClip((output_path), has_mask=True,target_resolution=(video_clip.w,video_clip.h)) 
        final_video = CompositeVideoClip([video_clip, overlay_clip]) 

        final_video.write_videofile( 
                final_path,
                fps=30,
                remove_temp=True,
                codec="libx264",
                audio_codec=False,
                preset = "ultrafast",  
                threads = 4,  
                logger=progress_callback,
            )
        final_video.close()        
