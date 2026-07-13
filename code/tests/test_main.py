"""主状态机安全停止行为测试。"""

# <!--A-->

import pathlib
import sys
import argparse
import unittest

import numpy as np


CODE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR / "sim"))

import execution  # noqa: E402
import main  # noqa: E402


POSE = {"x": 1.0, "y": 2.0, "deg": 0.0, "uv": (1, 2)}


class FakeScene:
    def __init__(self):
        self.was_placed = False

    def perturb(self):
        pass

    def place_block(self, *_args):
        self.was_placed = True


class FakeVision:
    def detect_board_pose(self, _image):
        return POSE

    def detect_blocks(self, _image, _board):
        return {"red": POSE}

    def slot_table_pos(self, _color, _board, _slots):
        return POSE


class MissingTargetVision(FakeVision):
    def detect_blocks(self, _image, _board):
        return {}


class FakeCognition:
    def parse_card2(self, _card, _now):
        return {
            "sequence": [
                {"step": 1, "block_color": "red", "tray_color": "blue"}
            ]
        }

    def check_confidence(self, _parsed):
        return True, None


class FailingRobot:
    def pick(self, *_args):
        raise execution.RobotExecutionError("PICK", "driver offline")

    def place(self, *_args):
        raise AssertionError("抓取失败后不应继续放置")


class FakeEvaluator:
    def score_pick(self, *_args):
        raise AssertionError("抓取失败后不应继续评分")


class FakeCamera:
    def capture(self):
        return np.zeros((600, 900, 3), dtype=np.uint8)


class FakeIO:
    def __init__(self):
        self.spoken = []
        self.lines = []

    def now(self):
        return "2026-07-13T00:00:00"

    def log(self, message):
        self.lines.append(message)

    def speak(self, message):
        self.spoken.append(message)


class MainSafetyTests(unittest.TestCase):
    def test_real_mode_is_blocked_until_perception_and_transform_are_ready(self):
        args = argparse.Namespace(
            mode="real",
            robot_host=None,
            robot_port=None,
            x_offset=None,
            y_offset=None,
            rotation_deg=None,
            scale=None,
        )

        with self.assertRaisesRegex(RuntimeError, "SimCamera"):
            main.create_robot(FakeIO(), args)

    def test_robot_failure_stops_task_and_does_not_place_block(self):
        scene = FakeScene()
        io = FakeIO()

        result = main.run_task2(
            scene,
            FakeVision(),
            FakeCognition(),
            FailingRobot(),
            FakeEvaluator(),
            FakeCamera(),
            io,
            {"blue": (0.0, 0.0)},
        )

        self.assertFalse(result)
        self.assertFalse(scene.was_placed)
        self.assertTrue(any("申请重抽任务卡" in message for message in io.spoken))
        self.assertTrue(any("安全停止" in line for line in io.lines))

    def test_missing_visual_target_stops_instead_of_skipping(self):
        scene = FakeScene()
        io = FakeIO()

        result = main.run_task2(
            scene,
            MissingTargetVision(),
            FakeCognition(),
            FailingRobot(),
            FakeEvaluator(),
            FakeCamera(),
            io,
            {"blue": (0.0, 0.0)},
        )

        self.assertFalse(result)
        self.assertFalse(scene.was_placed)
        self.assertTrue(any("申请重抽任务卡" in message for message in io.spoken))
        self.assertTrue(any("安全停止" in line for line in io.lines))


if __name__ == "__main__":
    unittest.main()
