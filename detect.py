import onnxruntime
import numpy as np
import cv2
import matplotlib.pyplot as plt
import time


def nms(pred, conf_thres, iou_thres):
    conf = pred[..., 4] > conf_thres
    box = pred[conf == True]
    cls_conf = box[..., 5:]
    cls = []
    for i in range(len(cls_conf)):
        cls.append(int(np.argmax(cls_conf[i])))

    total_cls = list(set(cls))
    output_box = []
    for i in range(len(total_cls)):
        clss = total_cls[i]
        cls_box = []
        for j in range(len(cls)):
            if cls[j] == clss:
                box[j][5] = clss
                cls_box.append(box[j][:6])

        cls_box = np.array(cls_box)
        box_conf = cls_box[..., 4]
        box_conf_sort = np.argsort(box_conf)
        max_conf_box = cls_box[box_conf_sort[len(box_conf) - 1]]
        output_box.append(max_conf_box)
        cls_box = np.delete(cls_box, 0, 0)
        while len(cls_box) > 0:
            max_conf_box = output_box[len(output_box) - 1]
            del_index = []
            for j in range(len(cls_box)):
                current_box = cls_box[j]
                interArea = getInter(max_conf_box, current_box)
                iou = getIou(max_conf_box, current_box, interArea)
                if iou > iou_thres:
                    del_index.append(j)
            cls_box = np.delete(cls_box, del_index, 0)
            if len(cls_box) > 0:
                output_box.append(cls_box[0])
                cls_box = np.delete(cls_box, 0, 0)
    return output_box


def getIou(box1, box2, inter_area):
    box1_area = box1[2] * box1[3]
    box2_area = box2[2] * box2[3]
    union = box1_area + box2_area - inter_area
    iou = inter_area / union
    return iou


def getInter(box1, box2):
    box1_x1, box1_y1, box1_x2, box1_y2 = box1[0] - box1[2] / 2, box1[1] - box1[3] / 2, \
                                         box1[0] + box1[2] / 2, box1[1] + box1[3] / 2
    box2_x1, box2_y1, box2_x2, box2_y2 = box2[0] - box2[2] / 2, box2[1] - box1[3] / 2, \
                                         box2[0] + box2[2] / 2, box2[1] + box2[3] / 2
    if box1_x1 > box2_x2 or box1_x2 < box2_x1:
        return 0
    if box1_y1 > box2_y2 or box1_y2 < box2_y1:
        return 0
    x_list = [box1_x1, box1_x2, box2_x1, box2_x2]
    x_list = np.sort(x_list)
    x_inter = x_list[2] - x_list[1]
    y_list = [box1_y1, box1_y2, box2_y1, box2_y2]
    y_list = np.sort(y_list)
    y_inter = y_list[2] - y_list[1]
    inter = x_inter * y_inter
    return inter


def draw(img, xscale, yscale, pred, fps):
    img_ = img.copy()
    if len(pred):
        for detect in pred:
            x1 = int(detect[0] / xscale)
            y1 = int(detect[1] / yscale)
            x2 = int(detect[2] / xscale)
            y2 = int(detect[3] / yscale)
            img_ = cv2.rectangle(img_, (x1, y1), (x2, y2), (0, 255, 0), 1)
    cv2.putText(img_, f"FPS: {fps}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return img_


def predict(model, image):
    height, width = 1280, 1280
    x_scale = image.shape[1] / width
    y_scale = image.shape[0] / height
    img = image / 255.
    img = cv2.resize(img, (width, height))
    img = np.transpose(img, (2, 0, 1))
    data = np.expand_dims(img, axis=0)
    input_name = model.get_inputs()[0].name
    label_name = model.get_outputs()[0].name
    pred = model.run([label_name], {input_name: data.astype(np.float32)})[0]
    pred = np.squeeze(pred)
    pred = np.transpose(pred, (1, 0))
    pred_class = pred[..., 4:]
    pred_conf = np.max(pred_class, axis=-1)
    pred = np.insert(pred, 4, pred_conf, axis=-1)
    result = nms(pred, 0.3, 0.45)  # confidence threshold & iou threshold

    new_result = []
    for detect in result:
        detect = [
            int((detect[0] - detect[2] / 2) * x_scale),
            int((detect[1] - detect[3] / 2) * y_scale),
            int((detect[0] + detect[2] / 2) * x_scale),
            int((detect[1] + detect[3] / 2) * y_scale), detect[4], detect[5]
        ]
        new_result.append(detect)
    new_result = np.array(new_result)
    # print(result)

    # ret_img = draw(img0, x_scale, y_scale, new_result)
    # ret_img = ret_img[:, :, ::-1]
    # plt.imshow(ret_img)
    # plt.show()

    return new_result


def detect_and_display(model):
    capture = cv2.VideoCapture(0)  # 打开摄像头，参数为摄像头索引号，0表示第一个摄像头
    fps_start_time = time.time()
    fps_counter = 0
    while True:
        ret, frame = capture.read()  # 读取摄像头图像
        if not ret:
            break

        result = predict(model, frame)  # 对图像进行检测

        # 在图像上绘制检测结果和帧数
        fps_counter += 1
        fps_current_time = time.time()
        fps = fps_counter / (fps_current_time - fps_start_time)
        img_with_boxes = draw(frame, 1, 1, result, round(fps, 2))
        cv2.imshow("Detection", img_with_boxes)

        if cv2.waitKey(1) == 27:  # 按下ESC键退出
            break

    capture.release()  # 释放摄像头
    cv2.destroyAllWindows()  # 关闭窗口


if __name__ == "__main__":

    onnx_model_path = r"models\cockroach\best.onnx"
    sess = onnxruntime.InferenceSession(onnx_model_path)

    # image_path = r"cockroach_112.jpg"
    # img0 = cv2.imread(image_path)

    detect_and_display(sess)
    # predict(sess, img0)
