@echo off
set NDK_OUT=E:\Documents\gogglesV2\builds\working_v3format\obj
set NDK_LIBS_OUT=E:\Documents\gogglesV2\builds\working_v3format\libs
call ndk-build NDK_PROJECT_PATH=. NDK_APPLICATION_MK=jni/Application.mk