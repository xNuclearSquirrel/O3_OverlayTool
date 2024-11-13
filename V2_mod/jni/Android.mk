LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE    := O3_OSD_recording
LOCAL_SRC_FILES := gs_lv_transcode_rec_omx_start.c MxDisplayPortDisplayPort_DrawScreen.c # Add all relevant hook files here


LOCAL_LDLIBS := -ldl

include $(BUILD_SHARED_LIBRARY)
