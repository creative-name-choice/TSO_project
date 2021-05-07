#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# File:        software/utils/loop.py
# By:          Samuel Duclos
# For:         Myself
# Description: This file implements the main loop for object detection with OpenCV.

IS_ARDUCAM = False

if IS_ARDUCAM:
    import arducam_config_parser, ArducamSDK
    from ImageConvert import *

from cvlib.object_detection import draw_bbox
from utils.inference import ObjectCenter
from copy import deepcopy

import cv2, os, sys, threading, time

global cfg, handle, running, Width, Height, save_flag, color_mode, save_raw

running = True
save_flag = False
save_raw = False
cfg = {}
handle = {}

def configBoard(config):
    global handle
    ArducamSDK.Py_ArduCam_setboardConfig(handle, 
                                         config.params[0], 
                                         config.params[1], 
                                         config.params[2], 
                                         config.params[3], 
                                         config.params[4:config.params_length])

def camera_initFromFile(fileName):
    global cfg, handle, Width, Height, color_mode, save_raw

    config = arducam_config_parser.LoadConfigFile(fileName)

    camera_parameter = config.camera_param.getdict()
    Width = camera_parameter["WIDTH"]
    Height = camera_parameter["HEIGHT"]

    BitWidth = camera_parameter["BIT_WIDTH"]
    ByteLength = 1

    if BitWidth > 8 and BitWidth <= 16:
        ByteLength = 2
        save_raw = True

    FmtMode = camera_parameter["FORMAT"][0]
    color_mode = camera_parameter["FORMAT"][1]
    print("color mode", color_mode)

    I2CMode = camera_parameter["I2C_MODE"]
    I2cAddr = camera_parameter["I2C_ADDR"]
    TransLvl = camera_parameter["TRANS_LVL"]

    cfg = {
        "u32CameraType": 0x00,
        "u32Width": Width,
        "u32Height": Height,
        "usbType": 0,
        "u8PixelBytes": ByteLength,
        "u16Vid": 0,
        "u32Size": 0,
        "u8PixelBits": BitWidth,
        "u32I2cAddr": I2cAddr,
        "emI2cMode": I2CMode,
        "emImageFmtMode": FmtMode,
        "u32TransLvl": TransLvl
    }

    ret, handle, rtn_cfg = ArducamSDK.Py_ArduCam_autoopen(cfg)

    if ret == 0:
        usb_version = rtn_cfg['usbType']
        configs = config.configs
        configs_length = config.configs_length

        for i in range(configs_length):
            type = configs[i].type

            if ((type >> 16) & 0xFF) != 0 and ((type >> 16) & 0xFF) != usb_version:
                continue

            if type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_REG:
                ArducamSDK.Py_ArduCam_writeSensorReg(handle, configs[i].params[0], configs[i].params[1])

            elif type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_DELAY:
                time.sleep(float(configs[i].params[0]) / 1000)

            elif type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_VRCMD:
                configBoard(configs[i])

        ArducamSDK.Py_ArduCam_registerCtrls(handle, config.controls, config.controls_length)
        ArducamSDK.Py_ArduCam_setCtrl(handle, "setFramerate", 5)

        rtn_val, datas = ArducamSDK.Py_ArduCam_readUserData(handle, 0x400 - 16, 16)

        print("Serial: %c%c%c%c-%c%c%c%c-%c%c%c%c" % (
                  datas[0], datas[1], datas[2], datas[3],
                  datas[4], datas[5], datas[6], datas[7],
                  datas[8], datas[9], datas[10], datas[11]
              ))

        return True

    else:
        print("open fail, rtn_val = ", ret)

        return False

def captureImage_thread():
    global handle, running

    rtn_val = ArducamSDK.Py_ArduCam_beginCaptureImage(handle)

    if rtn_val != 0:
        print("Error beginning capture, rtn_val = ", rtn_val)

        running = False

        return

    else:
        print("Capture began, rtn_val = ", rtn_val)

    while running:
        rtn_val = ArducamSDK.Py_ArduCam_captureImage(handle)

        if rtn_val > 255:
            print("Error capture image, rtn_val = ", rtn_val)

            if rtn_val == ArducamSDK.USB_CAMERA_USB_TASK_ERROR:
                break

        time.sleep(0.005)

    running = False
    ArducamSDK.Py_ArduCam_endCaptureImage(handle)

def readImage_thread():
    global handle, running, Width, Height, save_flag, cfg, color_mode, save_raw
    global COLOR_BayerGB2BGR, COLOR_BayerRG2BGR, COLOR_BayerGR2BGR, COLOR_BayerBG2BGR

    count = 0
    totalFrame = 0

    time0 = time.time()
    time1 = time.time()

    data = {}

    cv2.namedWindow("ArduCam Camarray", 1)

    if not os.path.exists("images"):
        os.makedirs("images")

    while running:
        display_time = time.time()

        if ArducamSDK.Py_ArduCam_availableImage(handle) > 0:		
            rtn_val, data, rtn_cfg = ArducamSDK.Py_ArduCam_readImage(handle)
            datasize = rtn_cfg['u32Size']

            if rtn_val != 0 or datasize == 0:
                ArducamSDK.Py_ArduCam_del(handle)

                print("Read data fail!")

                continue

            image = convert_image(data, rtn_cfg, color_mode)

            time1 = time.time()

            if time1 - time0 >= 1:
                print("%s %d %s\n" % ("fps:", count, "/s"))

                count = 0
                time0 = time1

            count += 1

            if save_flag:
                cv2.imwrite("images/image%d.jpg" % totalFrame, image)

                if save_raw:
                    with open("images/image%d.raw" % totalFrame, 'wb') as f:
                        f.write(data)

                totalFrame += 1

            image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_LINEAR)

            cv2.imshow("ArduCam Demo", image)
            cv2.waitKey(10)

            ArducamSDK.Py_ArduCam_del(handle)

        else:
            time.sleep(0.001)

def stream(args):
    print(" usage: sudo python ArduCam_Py_Demo.py <path/config-file-name>	\
        \n\n example: sudo python ArduCam_Py_Demo.py ../../../python_config/AR0134_960p_Color.json	\
        \n\n While the program is running, you can press the following buttons in the terminal:	\
        \n\n 's' + Enter:Save the image to the images folder.	\
        \n\n 'c' + Enter:Stop saving images.	\
        \n\n 'q' + Enter:Stop running the program.	\
        \n\n")

    try:
        if camera_initFromFile(args.config_file_name):
            ArducamSDK.Py_ArduCam_setMode(handle, ArducamSDK.CONTINUOUS_MODE)

            ct = threading.Thread(target=captureImage_thread)
            rt = threading.Thread(target=readImage_thread)
            ct.start()
            rt.start()

            while running:
                input_kb = str(sys.stdin.readline()).strip("\n")

                if input_kb == 'q' or input_kb == 'Q':
                    running = False

                if input_kb == 's' or input_kb == 'S':
                    save_flag = True

                if input_kb == 'c' or input_kb == 'C':
                    save_flag = False

            ct.join()
            rt.join()

            rtn_val = ArducamSDK.Py_ArduCam_close(handle)

            if rtn_val == 0:
                print("device close success!")

            else:
                print("device close fail!")

    except KeyboardInterrupt:
        print('User terminated stream process.')

    except Exception as e:
        print(e)

    finally:
        # Release resources.
        print('Done.')

def infer(frame, args, object_x=None, object_y=None, center_x=None, center_y=None):
    # Apply object detection.

    obj = ObjectCenter(args)

    predictions = obj.infer(frame, 
                            confidence=args.confidence_threshold, 
                            nms_thresh=args.nms_threshold, 
                            model=args.model, 
                            object_category=args.object_category, 
                            filter_objects=not args.no_filter_object_category)

    if predictions is not None and len(predictions) > 0:
        bbox, label, conf = predictions

        # Calculate the center of the frame since we will be trying to keep the object there.
        (H, W) = frame.shape[:2]
        center_x.value = W // 2
        center_y.value = H // 2

        object_location = obj.update(predictions, frame, (center_x.value, center_y.value))
        ((object_x.value, object_y.value), predictions) = object_location

        if args.no_show:
            return None

        else:
            # Draw bounding box over detected objects.
            inferred_image = draw_bbox(frame, bbox, label, conf, write_conf=True)
            return inferred_image

def loop(args, object_x=None, object_y=None, center_x=None, center_y=None):
    """Detection loop."""
    # Read input.
    if args.input_type == 'image':
        image = cv2.imread(args.image)

    elif args.input_type == 'video':
        cap = cv2.VideoCapture(args.video)

    elif args.input_type == 'camera':
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise SystemExit('ERROR: failed to open camera!')

    # Prepare arguments early.
    show = not args.no_show
    (height, width) = args.image_shape
    full_scrn = False
    fps = 0.0

    if show:
        from utils.display import open_window, set_display, show_fps
        open_window(args.video_name, 'Camera inference', width, height)

    else:
        out = cv2.VideoWriter(args.video_name, cv2.VideoWriter_fourcc(*'mp4v'), 30, (width, height))

    tic = time.time()

    try:
        # Loop through frames.
        while True:
            if not (args.input_type == 'image' or cap.isOpened()):
                break

            # Read frame from video/camera.
            if args.input_type == 'image':
                frame = deepcopy(image)

            elif cap.isOpened():
                status, frame = cap.read()

                if frame is None:
                    status, frame = cap.read()

                if not status:
                    break

            inferred_image = infer(frame, 
                                   args, 
                                   object_x=object_x, 
                                   object_y=object_y, 
                                   center_x=center_x, 
                                   center_y=center_y)

            if show:
                frame = show_fps(frame, fps)

                # Show raw inference results.
                cv2.imshow(args.video_name, frame)
            else:
                print('FPS:', fps)

            if args.save:
                # Save output.
                cv2.imwrite('object_detection_result.jpg', inferred_image)

            # Calculate an exponentially decaying average of FPS number.
            toc = time.time()
            curr_fps = 1.0 / (toc - tic)
            fps = curr_fps if fps == 0.0 else (fps * 0.95 + curr_fps * 0.05)
            tic = toc

            # Catch keyboard input.
            key = cv2.waitKey(1)

            # ESC key: quit program.
            if key == 27:
                break

            # Toggle fullscreen.
            elif show and (key == ord('F') or key == ord('f')):
                full_scrn = not full_scrn
                set_display(args.video_name, full_scrn)

    finally:
        # Release resources.
        if args.input_type != 'image':
            cap.release()

        cv2.destroyAllWindows()

