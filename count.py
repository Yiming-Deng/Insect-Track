import os
import csv

from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPainter


class MyLabel(QLabel):

    def __init__(self, parent=None):
        super(MyLabel, self).__init__(parent)
        self.add_camera_event = False
        self.rect_list = []
        self.pen_list = []
        self.new_rect = None

    def addRect(self, x0, y0, w, h, pen):
        self.pen_list.append(pen)
        self.new_rect = QRect(x0, y0, w, h)
        self.rect_list.append(self.new_rect)
        self.update()

        return [x0, y0, w, h, pen]

    def removeItem(self, item):
        self.rect_list.pop()
        self.pen_list.pop()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.add_camera_event and len(self.rect_list) > 0:
            painter = QPainter(self)
            for index in range(len(self.rect_list)):
                painter.setPen(self.pen_list[index])
                painter.drawRect(self.rect_list[index])


class InsectCount():

    def __init__(self, area_dict, width, height, fps, max, min):
        '''
        time_dict = {'a_dict':{'c1':[t1, t2, t3, ...],
                               'c2':[t1, t2, t3, ...],
                               'c3':[t1, t2, t3, ...],
                             ...},
                     'b_dict':...,
                     'c_dict':...,
                     ...}
        last_frame_dict={'c1':C1_COUNT_NUM,
                         'c2':C2_COUNT_NUM,
                         'c3':C3_COUNT_NUM,
                         ...}
        '''
        self.time_dict = {}
        self.last_frame_dict = {}
        self.area_list = []
        self.frame_threshold = fps * min
        self.same_target_threshold = fps * max
        for (key, value) in area_dict.items():
            self.time_dict[key + "_dict"] = {}
            self.area_list.append(self.areaAdjust(value[:-1], width, height))

    def areaAdjust(self, tlwh, width, height):
        temp_tlwh = [tlwh[0] / 796, tlwh[1] / 597, tlwh[2] / 796, tlwh[3] / 597]
        if width / height > (4 / 3):
            new_height = width * 3 / 4
            new_tlwh = [
                temp_tlwh[0] * width,
                temp_tlwh[1] * new_height - (new_height - height) / 2,
                temp_tlwh[2] * width,
                temp_tlwh[3] * new_height,
            ]
            if new_tlwh[1] < 0:
                new_tlwh[1] = 0
            if new_tlwh[1] + new_tlwh[3] > height:
                new_tlwh[3] = height - new_tlwh[1]
        elif width / height < (4 / 3):
            new_width = height * 4 / 3
            new_tlwh = [
                temp_tlwh[0] * new_width - (new_width - width) / 2,
                temp_tlwh[1] * height,
                temp_tlwh[2] * new_width,
                temp_tlwh[3] * height,
            ]
            if new_tlwh[0] < 0:
                new_tlwh[0] = 0
            if new_tlwh[0] + new_tlwh[2] > width:
                new_tlwh[2] = width - new_tlwh[0]
        else:
            new_tlwh = [
                temp_tlwh[0] * width,
                temp_tlwh[1] * height,
                temp_tlwh[2] * width,
                temp_tlwh[3] * height,
            ]

        return new_tlwh

    def judgeOverlap(self, tlwh0, tlwh1):
        box0 = [tlwh0[0], tlwh0[1], tlwh0[0] + tlwh0[2], tlwh0[1] + tlwh0[3]]  # x0 y0 x1 y1
        box1 = [tlwh1[0], tlwh1[1], tlwh1[0] + tlwh1[2], tlwh1[1] + tlwh1[3]]
        p0 = [max(box0[0], box1[0]), max(box0[1], box1[1])]  # x y
        p1 = [max(box0[2], box1[2]), max(box0[3], box1[3])]
        if p0[0] < p1[0] and p0[1] < p1[1]:
            return (p1[0] - p0[0]) * (p1[1] - p0[1])
        else:
            return 0

    def count(self, tlwh, id):
        overlap_area = []
        for area in self.area_list:
            overlap_area.append(self.judgeOverlap(tlwh, area))
        if overlap_area:
            if max(overlap_area) != 0:
                area_index = overlap_area.index(max(overlap_area))
                area_name = list(self.time_dict.keys())[area_index]
                if id in list(self.time_dict[area_name].keys()):
                    if id in list(self.last_frame_dict.keys()):
                        self.time_dict[area_name][id][-1] += 1
                        # self.last_frame_dict[id] = self.same_target_threshold
                    else:
                        self.time_dict[area_name][id].append(1)
                        # self.last_frame_dict[id] = self.same_target_threshold

                else:
                    self.time_dict[area_name][id] = [1]
                    # self.last_frame_dict[id] = self.same_target_threshold
                self.last_frame_dict[id] = self.same_target_threshold

    def update(self):
        for id in list(self.last_frame_dict.keys()):
            self.last_frame_dict[id] -= 1
            if self.last_frame_dict[id] == 0:
                self.last_frame_dict.pop(id)

    def save(self, path, fps):
        for (area_name, id_dict) in list(self.time_dict.items()):
            for (id, time_list) in list(id_dict.items()):
                for time_index in range(len(time_list)):
                    if time_list[time_index] < self.frame_threshold:
                        self.time_dict[area_name][id].pop(time_index)
                    else:
                        self.time_dict[area_name][id][time_index] /= fps
                if not self.time_dict[area_name][id]:
                    self.time_dict[area_name].pop(id)

        area_count = {}
        area_time = {}
        for area_name, id_dict in self.time_dict.items():
            area_count[area_name] = len(id_dict)
            area_time[area_name] = sum(sum(id_dict.values(), []))

        result_path = os.path.join(path, "result.csv")
        with open(result_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["area name", "num"])
            for row in area_count.items():
                writer.writerow(row)
            writer.writerow(["area name", "time(s)"])
            for row in area_time.items():
                writer.writerow(row)

        detail_path = os.path.join(path, "detail.csv")
        # df = pd.DataFrame(self.time_dict)
        # df.to_csv(detail_path, index=False)
        with open(detail_path, 'w', newline='') as f:
            writer = csv.writer(f)
            for (key, value) in list(self.time_dict.items()):
                writer.writerow([key])
                for (id, time_list) in list(value.items()):
                    time_list.insert(0, id)
                    writer.writerow(time_list)

        return area_count, area_time
