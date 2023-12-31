#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# File:        software/jetson/fastmot/videoio.py
# By:          Samuel Duclos
# For:         Myself
# Description: This file was adapted from FastMOT for uARM feedback control.
# Reference:   https://github.com/GeekAlexis/FastMOT.git

from pathlib import Path
from enum import Enum
from collections import deque
from urllib.parse import urlparse
import subprocess
import threading
import logging
import cv2

LOGGER = logging.getLogger(__name__)

IS_ARDUCAM = False

WITH_GSTREAMER = True

class Protocol(Enum):
    IMAGE = 0
    VIDEO = 1
    CSI   = 2
    V4L2  = 3
    RTSP  = 4
    HTTP  = 5

class VideoIO(object):
    """
    Class for capturing from a video file, an image sequence, or a camera, and saving video output.
    Encoding, decoding, and scaling can be accelerated using the GStreamer backend.
    Parameters
    ----------
    size : (int, int)
        Width and height of each frame to output.
    config : Dict
        Camera and buffer configuration.
    input_uri : string
        URI to an input video file or capturing device.
    output_uri : string
        URI to an output video file.
    proc_fps : int
        Estimated processing speed. This depends on compute and scene complexity.
    """

    def __init__(self, 
                 size, 
                 config, 
                 input_uri, 
                 output_uri=None, 
                 proc_fps=30, 
                 udp_port=1337, 
                 flip_vertically=False, 
                 flip_horizontally=False, 
                 is_rpi_cam=False, 
                 udp=False):

        self.size = size
        self.input_uri = input_uri
        self.output_uri = output_uri
        self.proc_fps = proc_fps
        self.flip_vertically = flip_vertically
        self.flip_horizontally = flip_horizontally
        self.is_rpi_cam = is_rpi_cam

        self.resolution = config['resolution']
        self.frame_rate = config['frame_rate']
        self.buffer_size = config['buffer_size']

        self.protocol = self._parse_uri(self.input_uri)
        self.is_live = self.protocol != Protocol.IMAGE and self.protocol != Protocol.VIDEO

        if is_rpi_cam:
            # To flip the image, modify the flip_method parameter (0 and 2 are the most common)
            #self.source = cv2.VideoCapture('/dev/video0', cv2.V4L2)
            print(self.gstreamer_pipeline(flip_method=0))
            self.source = cv2.VideoCapture(self.gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

        elif WITH_GSTREAMER:
            self.source = cv2.VideoCapture(self._gst_cap_pipeline(), cv2.CAP_GSTREAMER)

        else:
            self.source = cv2.VideoCapture(self.input_uri)

        self.frame_queue = deque([], maxlen=self.buffer_size)
        self.cond = threading.Condition()
        self.exit_event = threading.Event()
        self.cap_thread = threading.Thread(target=self._capture_frames)

        ret, frame = self.source.read()
        if not ret:
            raise RuntimeError('Unable to read video stream')
        self.frame_queue.append(frame)

        width = self.source.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.source.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.cap_fps = self.source.get(cv2.CAP_PROP_FPS)
        self.do_resize = (width, height) != self.size
        if self.cap_fps == 0:
            self.cap_fps = self.frame_rate # fallback to config if unknown
        LOGGER.info('%dx%d stream @ %d FPS', width, height, self.cap_fps)

        if self.output_uri is not None:
            Path(self.output_uri).parent.mkdir(parents=True, exist_ok=True)
            output_fps = 1 / self.cap_dt
            if WITH_GSTREAMER:
                self.writer = cv2.VideoWriter(self._gst_write_pipeline(), cv2.CAP_GSTREAMER, 0,
                                              output_fps, self.size, True)
            else:
                fourcc = cv2.VideoWriter_fourcc(*'avc1')
                self.writer = cv2.VideoWriter(self.output_uri, fourcc, output_fps, self.size, True)

    # gstreamer_pipeline returns a GStreamer pipeline for capturing from the CSI camera
    # Defaults to 1280x720 @ 60fps
    # Flip the image by setting the flip_method (most common values: 0 and 2)
    # display_width and display_height determine the size of the window on the screen
    def gstreamer_pipeline(
        self,
        capture_width=3820,
        capture_height=2464,
        display_width=960,
        display_height=616,
        framerate=21,
        flip_method=0,
    ):
        #return (
        #    "nvarguscamerasrc ! "
        #    "video/x-raw(memory:NVMM), "
        #    "width=(int)%d, height=(int)%d, "
        #    "format=(string)NV12, framerate=(fraction)%d/1 ! "
        #    "nvvidconv flip-method=%d ! "
        #    "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        #    "videoconvert ! "
        #    "video/x-raw, format=(string)BGR ! appsink"
        #    % (
        #        capture_width,
        #        capture_height,
        #        framerate,
        #        flip_method,
        #        display_width,
        #        display_height,
        #    )
        #return 'nvarguscamerasrc ! video/x-raw(memory:NVMM), width=3280, height=2464, format=(string)NV12, framerate=21/1 ! nvvidconv flip-method=0 ! video/x-raw, width=960, height=616, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink wait-on-eos=false max-buffers=1 drop=True'
        #return 'nvarguscamerasrc ! video/x-raw(memory:NVMM), width=3820, height=2464, format=(string)NV12, framerate=21/1 ! nvvidconv flip-method=0 ! video/x-raw, width=960, height=616, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink max-buffers=1 drop=True'
        return 'nvarguscamerasrc wbmode=3 tnr-mode=2 tnr-strength=1 ee-mode=2 ee-strength=1 ! video/x-raw(memory:NVMM), width=3264, height=2464, format=NV12, framerate=21/1 ! nvvidconv flip-method=0 ! video/x-raw, width=960, height=616, format=BGRx ! videoconvert ! video/x-raw, format=BGR ! videobalance contrast=1.5 brightness=-.2 saturation=1.2 ! appsink'

    @property
    def cap_dt(self):
        # limit capture interval at processing latency for live sources
        return 1 / min(self.cap_fps, self.proc_fps) if self.is_live else 1 / self.cap_fps

    def start_capture(self):
        """
        Start capturing from file or device.
        """
        if not self.source.isOpened():
            self.source.open(self.gstreamer_pipeline() if self.is_rpi_cam else self._gst_cap_pipeline(), cv2.CAP_GSTREAMER)
        if not self.cap_thread.is_alive():
            self.cap_thread.start()

    def stop_capture(self):
        """
        Stop capturing from file or device.
        """
        with self.cond:
            self.exit_event.set()
            self.cond.notify()
        self.frame_queue.clear()
        self.cap_thread.join()

    def read(self):
        """
        Returns the next video frame.
        Returns None if there are no more frames.
        """
        with self.cond:
            while len(self.frame_queue) == 0 and not self.exit_event.is_set():
                self.cond.wait()
            if len(self.frame_queue) == 0 and self.exit_event.is_set():
                return None
            frame = self.frame_queue.popleft()
            self.cond.notify()
        if self.do_resize:
            frame = cv2.resize(frame, self.size)
        return frame

    def write(self, frame):
        """
        Writes the next video frame.
        """
        assert hasattr(self, 'writer')
        self.writer.write(frame)

    def release(self):
        """
        Closes video file or capturing device.
        """
        self.stop_capture()
        if hasattr(self, 'writer'):
            self.writer.release()
        self.source.release()

    def _gst_cap_pipeline(self):
        gst_elements = str(subprocess.check_output('gst-inspect-1.0'))
        if IS_ARDUCAM:
            cvt_pipeline = (
                'nvvidconv interpolation-method=5 ! ' #'nvvidconv ! '
                'video/x-raw(memory:NVMM), format=(string)I420 ! '
                'videoconvert ! appsink sync=false'
            )
        else:
            if 'nvvidconv' in gst_elements and self.protocol != Protocol.V4L2:
                # format conversion for hardware decoder
                cvt_pipeline = (
                    'nvvidconv interpolation-method=5 ! '
                    'video/x-raw, width=%d, height=%d, format=BGRx !'
                    'videoconvert ! appsink sync=false'
                    % self.size
                )
            else:
                cvt_pipeline = (
                    'videoscale ! '
                    'video/x-raw, width=%d, height=%d !'
                    'videoconvert ! appsink sync=false'
                    % self.size
                )

        if self.protocol == Protocol.IMAGE:
            pipeline = (
                'multifilesrc location=%s index=1 caps="image/%s,framerate=%d/1" ! decodebin ! '
                % (
                    self.input_uri,
                    self._img_format(self.input_uri),
                    self.frame_rate
                )
            )
        elif self.protocol == Protocol.VIDEO:
            pipeline = 'filesrc location=%s ! decodebin ! ' % self.input_uri
        elif self.protocol == Protocol.CSI:
            if IS_ARDUCAM:
                pipeline = (
                    'nvarguscamerasrc sensor_id=%s ! '
                    'video/x-raw, format=(string)I420, width=(int)%d, height=(int)%d, framerate=(fraction)80/1 ! ' % self.resolution
                )
            elif 'nvarguscamerasrc' in gst_elements:
                pipeline = (
                    'nvarguscamerasrc sensor_id=%s ! '
                    'video/x-raw(memory:NVMM), width=%d, height=%d, '
                    'format=NV12, framerate=%d/1 ! '
                    % (
                        self.input_uri[6:],
                        *self.resolution,
                        self.frame_rate
                    )
                )
            else:
                raise RuntimeError('GStreamer CSI plugin not found')
        elif self.protocol == Protocol.V4L2:
            if 'v4l2src' in gst_elements:
                pipeline = (
                    'v4l2src device=%s ! '
                    'video/x-raw, width=%d, height=%d, '
                    'format=YUY2, framerate=%d/1 ! '
                    % (
                        self.input_uri,
                        *self.resolution,
                        self.frame_rate
                    )
                )
            else:
                raise RuntimeError('GStreamer V4L2 plugin not found')
        elif self.protocol == Protocol.RTSP:
            pipeline = 'rtspsrc location=%s latency=0 ! decodebin ! ' % self.input_uri
        elif self.protocol == Protocol.HTTP:
            pipeline = 'souphttpsrc location=%s is-live=true ! decodebin ! ' % self.input_uri
        return pipeline + cvt_pipeline

    def _gst_write_pipeline(self):
        gst_elements = str(subprocess.check_output('gst-inspect-1.0'))
        # use hardware encoder if found
        if IS_ARDUCAM:
            h264_encoder = (
                'omxh264enc profile=high cabac-entropy-coding=true insert-sps-pps=true iframeinterval=60' #' ! video/x-h264, level=(string)4.2, stream-format=(string)byte-stream'
            )
        elif 'omxh264enc' in gst_elements:
            h264_encoder = 'omxh264enc preset-level=2'
        elif 'x264enc' in gst_elements:
            h264_encoder = 'x264enc'
        else:
            raise RuntimeError('GStreamer H.264 encoder not found')
        pipeline = (
            'appsrc ! autovideoconvert ! %s ! qtmux ! filesink location=%s '
            % (
                h264_encoder,
                self.output_uri
            )
        )
        return pipeline

    def _capture_frames(self):
        while not self.exit_event.is_set():
            ret, frame = self.source.read()

            if self.flip_vertically:
                frame = cv2.flip(frame, 0)

            if self.flip_horizontally:
                frame = cv2.flip(frame, 1)

            with self.cond:
                if not ret:
                    self.exit_event.set()
                    self.cond.notify()
                    break
                # Keep unprocessed frames in the buffer for file.
                if not self.is_live:
                    while (len(self.frame_queue) == self.buffer_size and
                           not self.exit_event.is_set()):
                        self.cond.wait()
                self.frame_queue.append(frame)
                self.cond.notify()

    @staticmethod
    def _parse_uri(uri):
        result = urlparse(uri)
        if result.scheme == 'csi':
            protocol = Protocol.CSI
        elif result.scheme == 'rtsp':
            protocol = Protocol.RTSP
        elif result.scheme == 'http':
            protocol = Protocol.HTTP
        else:
            if '/dev/video' in result.path:
                protocol = Protocol.V4L2
            elif '%' in result.path:
                protocol = Protocol.IMAGE
            else:
                protocol = Protocol.VIDEO
        return protocol

    @staticmethod
    def _img_format(uri):
        img_format = Path(uri).suffix[1:]
        return 'jpeg' if img_format == 'jpg' else img_format
