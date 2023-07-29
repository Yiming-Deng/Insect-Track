# InsectTrack
## Project Overview
The project completed the implementation of an insect detection and tracking software based on yolov8 and bot-sort, and supported labeling the area of interest and recording the number and time of insects entering the area. The software supports both camera-based real-time tracking detection and video-based tracking detection analysis. The specific usage method will be explained below.


## Software Function
The object detection function of the software is based on the yolov8 object detection model, which supports the identification of other arbitrary objects by changing the model file. The area drawing function can draw multiple rectangular boxes (supporting addition, deletion, display and hiding) as areas of interest in the camera screen or video recording, record and time each target entering the area, and save the results to the form file after the detection is completed. The target tracking function can give a number to each detected target to distinguish different targets, so that the counting function is more accurate.


## Instructions


1. Download "InsectTrack.zip" of InsectTrack Software in Releases and unzip it.
2. Run "LAVFilters-0.77.2-Installer.exe" to complete the installation of video format patches, so as to achieve software support for videos in different formats.
3. Open the "main" folder, find "main.exe" and run it (the file icon is an ant, it should be easy to find).
4. On the right side of the software interface, "Monitoring Area Setting" can select the area of interest in the left area, click "Add" button, press and drag the left mouse button in the left area, release the left button to complete the box selection, and "Delete" button can delete the last area. "Show\Hide" can show \ hide the selected area.
5. "Max Detection Interval" indicates the maximum time for a previously detected target to leave the region. If the target is not in the region for the duration of this time, the target is considered to have left the region. Min Continuous Detection Time" indicates that the target detected in a region is regarded as the minimum time threshold for entering the region. The target is regarded as appearing in the region only when the target is continuously in the region.
6. The left side of the software interface distinguishes between camera detection and video detection functions.
7. Camera detection: the "Chosse Camera" in the upper right corner can select any identified camera and open it (identification will only be performed when opening the software), and the "Choose Insect" can be used to select the type of insect recognized (cockroaches and ants). Under "Choose model", you can choose the model Path, or choose the Default path through "Default Path". You can also directly enter the path in the text box. If you want to record and Save images and records based on camera recognition, you need to select "Video Save Path" as the saving path for video and analysis results. Finally, press "Track Switch" to start real-time tracking analysis.
8. Video detection: in the upper right corner, "Choose Insect" can be used to select the insect species (cockroaches and ants); Choose model" You can choose a model Path or use "Default Path" to select a default path. You can also directly enter a path in the text box. The "Choose Video" below is used to select the video, and also saves the path as the path for subsequent videos and analysis results. Press "Open Video" to preview the selected video; Press "Track Switch" to start real-time tracking analysis; The analysis progress will be displayed in the upper right corner.
9. After the inspection is complete, a folder named after the time the inspection started will be generated in the save path with the trace result video, "result.csv", and "detail.csv". result.csv" counts the total number and time of insects that have entered each area;" Detail.csv "records each area, each target, and each entry time in detail.


## Software Screenshot

![camera](/image/camera.png "Camera")

![video](/image/video.png "Video")


## Else

If you find any problems or errors in use, please leave a comment.


## Copyright and License

The code and documentation of this project are released under the MIT License. You are free to use and modify the code and documentation of this project as long as you comply with the license terms. Please acknowledge the source and author information of this project when using or distributing it.
