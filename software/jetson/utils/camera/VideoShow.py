#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# File:        software/utils/camera/VideoShow.py
# By:          Samuel Duclos
# For:         Myself
# Description: This file implements a frame "show"-er on a dedicated thread for the camera program.
# Reference:   https://github.com/nrsyed/computer-vision.git

from threading import Thread
import cv2

class VideoShow:
    """Class that continuously shows a frame using a dedicated thread."""
    def __init__(self, frame=None):
        self.frame = frame
        self.stopped = False

    def start(self):
        Thread(target=self.show, args=()).start()
        return self

    def show(self):
        while not self.stopped:
            if self.frame is not None:
                cv2.imshow('uARM', self.frame)

            if cv2.waitKey(1) == ord('q'):
                self.stopped = True

    def stop(self):
        self.stopped = True

