"""
annotate.py — 可视化标注 (对应评分细则: 实时展示识别框/坐标/当前步骤)

- 自由方块: 绿色旋转框 + 中心 + 台面坐标 + 角度。
- 托盘板: 蓝色外轮廓框 + 板中心十字 (展示板位姿检测结果)。
- 各色槽: 由板位姿+标定布局算出的位置, 画标记+颜色名 (被遮挡时同样标出)。
- 当前步骤高亮: 红框圈当前方块, 黄框圈目标槽。
"""
import math
import numpy as np
import cv2
import config as C


def _rot_pts_px(uv, side_mm, deg):
    cu, cv = uv
    half = side_mm * C.PX_PER_MM
    return np.round(cv2.boxPoints(((cu, cv), (half, half), deg))).astype(np.int32)


def _board_rect_px(board):
    cu, cv = board["uv"]
    bw = C.TRAY_BOARD_W_MM * C.PX_PER_MM
    bh = C.TRAY_BOARD_H_MM * C.PX_PER_MM
    return np.round(cv2.boxPoints(((cu, cv), (bw, bh), board["deg"]))).astype(np.int32)


def draw(img, board, slot_local, blocks, title="", highlight=None):
    out = img.copy()
    # 托盘板外轮廓 (板位姿检测的依据)
    if board is not None:
        cv2.polylines(out, [_board_rect_px(board)], True, (255, 150, 0), 2, cv2.LINE_AA)
        cv2.drawMarker(out, board["uv"], (255, 150, 0), cv2.MARKER_CROSS, 18, 2)
        cv2.putText(out, "tray board", (board["uv"][0]-30, board["uv"][1]-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 150, 0), 1, cv2.LINE_AA)
        # 各色槽 (由板位姿+布局算出, 被遮挡时同样标出)
        import vision
        for color in C.COLORS:
            if color in slot_local:
                s = vision.slot_table_pos(color, board, slot_local)
                cv2.drawMarker(out, s["uv"], (0, 170, 255), cv2.MARKER_TILTED_CROSS, 12, 2)
                cv2.putText(out, color, (s["uv"][0]-16, s["uv"][1]+24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 140, 220), 1, cv2.LINE_AA)
    # 自由方块
    for color, rec in blocks.items():
        u, v = rec["uv"]
        cv2.polylines(out, [_rot_pts_px(rec["uv"], C.BLOCK_MM, rec["deg"])], True,
                      (0, 255, 0), 2, cv2.LINE_AA)
        cv2.circle(out, (u, v), 3, (0, 255, 0), -1)
        cv2.putText(out, f"{color} {rec['deg']:+.0f}d", (u-24, v-16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.putText(out, f"({rec['x']:.0f},{rec['y']:.0f})", (u-28, v+22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 200, 0), 1, cv2.LINE_AA)
    # 当前步骤高亮
    if highlight and board is not None:
        import vision
        bc, tc = highlight
        if bc in blocks:
            cv2.polylines(out, [_rot_pts_px(blocks[bc]["uv"], C.BLOCK_MM+8, blocks[bc]["deg"])],
                          True, (0, 0, 255), 2, cv2.LINE_AA)
        if tc in slot_local:
            s = vision.slot_table_pos(tc, board, slot_local)
            cv2.polylines(out, [_rot_pts_px(s["uv"], C.TRAY_SLOT_MM, s["deg"])],
                          True, (0, 220, 255), 2, cv2.LINE_AA)
    if title:
        cv2.rectangle(out, (0, 0), (C.IMG_W, 26), (40, 40, 40), -1)
        cv2.putText(out, title, (8, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out
