import os
import time
import cv2
import onnxruntime
import argparse

from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QImage, QImage, QPixmap

from detect import predict
from tracker.bot_sort import BoTSORT
from tracker.tracking_utils.timer import Timer
from tracker.visualize import plot_tracking

from count import InsectCount

HEIGHT = 601
WIDTH = 801


def make_parser():
    parser = argparse.ArgumentParser("BoT-SORT Demo!")
    # parser.add_argument("demo", default="webcam", help="demo type, eg. image, video and webcam")
    parser.add_argument("-expn", "--experiment-name", type=str, default=None)
    parser.add_argument("-n", "--name", type=str, default=None, help="model name")
    parser.add_argument("--path", default="", help="path to images or video")
    parser.add_argument("--camid", type=int, default=0, help="webcam demo camera id")
    parser.add_argument("--save_result",
                        action="store_true",
                        help="whether to save the inference result of image/video")
    parser.add_argument("-f", "--exp_file", default=None, type=str, help="pls input your expriment description file")
    parser.add_argument("-c", "--ckpt", default=None, type=str, help="ckpt for eval")
    parser.add_argument("--device", default="gpu", type=str, help="device to run our model, can either be cpu or gpu")
    parser.add_argument("--conf", default=None, type=float, help="test conf")
    parser.add_argument("--nms", default=None, type=float, help="test nms threshold")
    parser.add_argument("--tsize", default=None, type=int, help="test img size")
    parser.add_argument("--fps", default=30, type=int, help="frame rate (fps)")
    parser.add_argument("--fp16",
                        dest="fp16",
                        default=False,
                        action="store_true",
                        help="Adopting mix precision evaluating.")
    parser.add_argument("--fuse", dest="fuse", default=False, action="store_true", help="Fuse conv and bn for testing.")
    parser.add_argument("--trt",
                        dest="trt",
                        default=False,
                        action="store_true",
                        help="Using TensorRT model for testing.")

    # tracking args
    parser.add_argument("--track_high_thresh", type=float, default=0.1, help="tracking confidence threshold")
    parser.add_argument("--track_low_thresh", default=0.05, type=float, help="lowest detection threshold")
    parser.add_argument("--new_track_thresh", default=0.8, type=float, help="new track thresh")
    parser.add_argument("--track_buffer", type=int, default=360, help="the frames for keep lost tracks")
    parser.add_argument("--match_thresh", type=float, default=0.99, help="matching threshold for tracking")
    parser.add_argument(
        "--aspect_ratio_thresh",
        type=float,
        default=10,  # 1.6
        help="threshold for filtering out boxes of which aspect ratio are above the given value.")
    parser.add_argument('--min_box_area', type=float, default=10, help='filter out tiny boxes')
    parser.add_argument("--fuse-score",
                        dest="fuse_score",
                        default=False,
                        action="store_true",
                        help="fuse score and iou for association")

    # CMC
    parser.add_argument("--cmc-method",
                        default="sparseOptFlow",
                        type=str,
                        help="cmc method: files (Vidstab GMC) | orb | ecc")

    # ReID
    parser.add_argument("--with-reid", dest="with_reid", default=False, action="store_true", help="test mot20.")
    parser.add_argument("--fast-reid-config",
                        dest="fast_reid_config",
                        default=r"fast_reid/configs/MOT17/sbs_S50.yml",
                        type=str,
                        help="reid config file path")
    parser.add_argument("--fast-reid-weights",
                        dest="fast_reid_weights",
                        default=r"pretrained/mot17_sbs_S50.pth",
                        type=str,
                        help="reid config file path")
    parser.add_argument('--proximity_thresh',
                        type=float,
                        default=0.5,
                        help='threshold for rejecting low overlap reid matches')
    parser.add_argument('--appearance_thresh',
                        type=float,
                        default=0.25,
                        help='threshold for rejecting low appearance similarity reid matches')
    return parser


def padding(image):
    height, width = image.shape[:2]
    if width / height > 4 / 3:
        height_padding = width * 0.75 - height
        image_copy = cv2.copyMakeBorder(image,
                                        int(height_padding / 2),
                                        int(height_padding / 2),
                                        0,
                                        0,
                                        cv2.BORDER_CONSTANT,
                                        value=[0, 0, 0])
    elif width / height < 4 / 3:
        width_padding = height * 4 / 3 - width
        image_copy = cv2.copyMakeBorder(image,
                                        0,
                                        0,
                                        int(width_padding / 2),
                                        int(width_padding / 2),
                                        cv2.BORDER_CONSTANT,
                                        value=[0, 0, 0])
    else:
        image_copy = image
    image_show = cv2.resize(image_copy, (WIDTH, HEIGHT))

    return image_show


class OpenCamera(QThread):
    close_camera_signal = QtCore.pyqtSignal(int)
    track_signal = QtCore.pyqtSignal(bool, onnxruntime.InferenceSession, str, bool, dict, float, float)

    def __init__(self, view_signal, opened_signal, finish_camera_signal):
        super(OpenCamera, self).__init__()
        self.close_camera_signal.connect(self.closeCamera)
        self.track_signal.connect(self.trackSwitch)

        self.timer = Timer()
        self.view_signal = view_signal
        self.opened_signal = opened_signal
        self.finish_camera_signal = finish_camera_signal
        self.camer_num = 0
        self.time_flag = 1
        self.track = 0
        self.save = False
        self.vid_writer = None
        self.fps = 30

    def trackSwitch(self, switch, model, video_save_path, save_switch, video_area_dict, max, min):
        if switch:
            self.track = 1
            self.frame_id = 0
            self.model = model
            self.args = make_parser().parse_args()
            self.args.ablation = False
            self.args.mot20 = not self.args.fuse_score

            self.tracker = BoTSORT(self.args, frame_rate=self.fps)
            self.result = []

            # count
            self.video_count = InsectCount(video_area_dict, self.width, self.height, self.fps, max, min)

            if save_switch:
                self.video_save_path = os.path.join(video_save_path, time.strftime("%Y_%m_%d_%H_%M_%S",
                                                                                   time.localtime()))
                os.makedirs(self.video_save_path, exist_ok=True)
                self.video_path = os.path.join(self.video_save_path, "camera.avi")
                self.save = True
                self.vid_writer = cv2.VideoWriter(self.video_path, cv2.VideoWriter_fourcc(*"MJPG"), self.fps,
                                                  (int(self.width), int(self.height)))

        else:
            self.track = 0
            self.model = None
            if save_switch:
                num, times = self.video_count.save(self.video_save_path, self.fps)
                self.finish_camera_signal.emit(num, times)

    def openCamera(self):
        self.time_flag = 1
        self.cap = cv2.VideoCapture(self.camer_num, cv2.CAP_DSHOW)
        self.cap.set(3, 1600)
        self.cap.set(4, 1600)
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def closeCamera(self):
        self.time_flag = 0
        self.cap.release()

    def showImage(self):
        flag, self.image = self.cap.read()

        if flag and self.time_flag:
            self.image = cv2.flip(self.image, 1)

            if self.track:
                self.timer.tic()
                output = predict(self.model, self.image)
                if output is not None:
                    online_targets = self.tracker.update(output, self.image)
                    online_tlwhs = []
                    online_ids = []
                    online_scores = []
                    for t in online_targets:
                        tlwh = t.tlwh
                        tid = t.track_id
                        vertical = tlwh[2] / tlwh[3] > self.args.aspect_ratio_thresh
                        if tlwh[2] * tlwh[3] > self.args.min_box_area and not vertical:
                            self.video_count.count(tlwh, tid)

                            online_tlwhs.append(tlwh)
                            online_ids.append(tid)
                            online_scores.append(t.score)
                            self.result.append(
                                f"{self.frame_id},{tid},{tlwh[0]:.2f},{tlwh[1]:.2f},{tlwh[2]:.2f},{tlwh[3]:.2f},{t.score:.2f},-1,-1,-1\n"
                            )
                    self.timer.toc()
                    fps = 1. / self.timer.average_time
                    online_im = plot_tracking(self.image, online_tlwhs, online_ids, frame_id=self.frame_id + 1, fps=fps)
                    self.video_count.update()

                else:
                    self.timer.toc()
                    online_im = self.image
                if self.save:
                    adjusted_frame_interval = int(self.fps / fps)
                    for _ in range(adjusted_frame_interval):
                        self.vid_writer.write(online_im)
                self.frame_id += 1
            elif self.save:
                self.save = False
                self.vid_writer.release()

            image_show = padding(online_im if self.track else self.image)

            image_show = cv2.cvtColor(image_show, cv2.COLOR_BGR2RGB)
            camera_image = QtGui.QImage(image_show.data, WIDTH, HEIGHT, WIDTH * 3, QImage.Format_RGB888)
            camera_pixmap = QPixmap.fromImage(camera_image)
            if self.time_flag:
                self.view_signal.emit(camera_pixmap)
            camera_image.detach()

    def run(self):
        self.openCamera()
        self.opened_signal.emit(1)
        while self.time_flag:
            self.showImage()


class VideoProcess(QThread):
    track_signal = QtCore.pyqtSignal(onnxruntime.InferenceSession, str, dict, float, float)
    stop_signal = QtCore.pyqtSignal(int)

    def __init__(self, video_frame_signal, finish_video_signal):
        super(VideoProcess, self).__init__()
        self.video_path = ''
        self.timer = Timer()
        self.track = 0
        self.video_frame_signal = video_frame_signal
        self.finish_video_signal = finish_video_signal
        self.track_signal.connect(self.trackSwitch)
        self.stop_signal.connect(self.stopTrack)
        self.count = False

    def stopTrack(self):
        self.track = 0

    def trackSwitch(self, model, video_path, video_area_dict, max, min):

        self.video_path = video_path
        self.track = 1
        self.frame_id = 0
        self.model = model
        self.args = make_parser().parse_args()
        self.args.ablation = False
        self.args.mot20 = not self.args.fuse_score

        self.openVideo()

        self.tracker = BoTSORT(self.args, frame_rate=self.fps)
        self.result = []

        self.video_save_path = os.path.split(self.video_path)[0]
        self.video_save_path = os.path.join(self.video_save_path, time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))
        os.makedirs(self.video_save_path, exist_ok=True)
        self.video_path = os.path.join(self.video_save_path, "video.avi")
        self.save = True
        self.vid_writer = cv2.VideoWriter(self.video_path, cv2.VideoWriter_fourcc(*"MJPG"), self.fps,
                                          (int(self.width), int(self.height)))

        # count
        self.video_count = InsectCount(video_area_dict, self.width, self.height, self.fps, max, min)

    def openVideo(self):
        self.cap = cv2.VideoCapture(self.video_path)

        # self.cap.set(3, 1600)
        # self.cap.set(4, 1600)

        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.tot_frame = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)

        # info = ffmpeg.probe(self.video_path)
        # video_streams = next(c for c in info['streams'] if c['codec_type'] == 'video')
        # self.fps = int(video_streams['r_frame_rate'].split('/')[0])
        # self.width = int(video_streams['width'])
        # self.height = int(video_streams['height'])
        # self.tot_frame = int(video_streams['nb_frames'])
        # print(self.width, self.height, self.fps, self.tot_frame)

        # print(self.video_path)
        # video = VideoFileClip(self.video_path)
        # fps = video.fps
        # tot_frame = int(video.duration * fps)
        # print(fps, tot_frame)

    def videoTrack(self):
        if self.track:
            flag, self.image = self.cap.read()

            if flag:
                # self.image = cv2.flip(self.image, 1)

                self.timer.tic()
                output = predict(self.model, self.image)
                if output is not None:
                    online_targets = self.tracker.update(output, self.image)
                    online_tlwhs = []
                    online_ids = []
                    online_scores = []
                    for t in online_targets:
                        tlwh = t.tlwh
                        tid = t.track_id
                        vertical = tlwh[2] / tlwh[3] > self.args.aspect_ratio_thresh
                        if tlwh[2] * tlwh[3] > self.args.min_box_area and not vertical:
                            self.video_count.count(tlwh, tid)

                            online_tlwhs.append(tlwh)
                            online_ids.append(tid)
                            online_scores.append(t.score)
                            self.result.append(
                                f"{self.frame_id},{tid},{tlwh[0]:.2f},{tlwh[1]:.2f},{tlwh[2]:.2f},{tlwh[3]:.2f},{t.score:.2f},-1,-1,-1\n"
                            )
                    self.timer.toc()
                    fps = 1. / self.timer.average_time
                    online_im = plot_tracking(self.image, online_tlwhs, online_ids, frame_id=self.frame_id + 1, fps=fps)
                    self.video_count.update()
                else:
                    self.timer.toc()
                    online_im = self.image

                self.vid_writer.write(online_im)
                self.frame_id += 1
                self.video_frame_signal.emit(self.frame_id, self.tot_frame)

    def finishTrack(self):
        self.track = 0
        self.model = None
        self.vid_writer.release()

        num, time = self.video_count.save(self.video_save_path, self.fps)
        self.finish_video_signal.emit(num, time)

    def run(self):
        while self.track:
            self.videoTrack()
            if self.frame_id == self.tot_frame:
                break
        self.finishTrack()
