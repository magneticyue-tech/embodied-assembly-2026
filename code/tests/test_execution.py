"""执行层坐标、通信与失败传播测试。"""

# <!--A-->

import argparse
import json
import pathlib
import socket
import sys
import unittest


CODE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR / "sim"))
sys.path.insert(0, str(CODE_DIR / "execution"))

import execution  # noqa: E402


class DummyIO:
    def __init__(self):
        self.lines = []

    def log(self, message):
        self.lines.append(message)


class StubCommunicator:
    def __init__(self, response):
        self.response = response

    def send_command(self, _command):
        return self.response

    def close(self):
        pass


class TimeoutSocket:
    def __init__(self):
        self.payloads = []

    def sendto(self, payload, _address):
        self.payloads.append(payload)

    def recvfrom(self, _size):
        raise socket.timeout

    def close(self):
        pass


class IntegerSuccessSocket:
    def sendto(self, _payload, _address):
        pass

    def recvfrom(self, _size):
        return b'{"success":1,"message":"invalid","request_id":"fixed123"}', (
            "127.0.0.1",
            5000,
        )

    def close(self):
        pass


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.pose = {"x": 10.0, "y": 20.0, "deg": 5.0, "uv": (1, 2)}

    def test_aubo_pick_failure_raises_execution_error(self):
        robot = execution.AuboRobot(DummyIO())
        robot.comm = StubCommunicator({"success": False, "message": "offline"})

        with self.assertRaisesRegex(execution.RobotExecutionError, "offline"):
            robot.pick("red", self.pose)

    def test_partial_transform_arguments_merge_with_defaults(self):
        args = argparse.Namespace(
            mode=None,
            robot_host=None,
            robot_port=None,
            x_offset=12.0,
            y_offset=None,
            rotation_deg=None,
            scale=None,
        )
        config = execution.apply_args_to_config(args)["TRANSFORM_CONFIG"]

        self.assertEqual(
            set(config), {"x_offset", "y_offset", "rotation_deg", "scale"}
        )
        self.assertEqual(config["x_offset"], 12.0)

    def test_zero_transform_scale_is_rejected(self):
        config = dict(execution.DEFAULT_TRANSFORM_CONFIG, scale=0.0)

        with self.assertRaisesRegex(ValueError, "scale"):
            execution.table_to_robot(1.0, 2.0, 3.0, config)

    def test_udp_retries_reuse_one_request_id_and_payload(self):
        communicator = execution.RobotCommunicator(max_retries=3, retry_delay=0)
        fake_socket = TimeoutSocket()
        communicator.socket = fake_socket
        communicator._generate_request_id = lambda: "fixed123"

        response = communicator.send_command({"cmd": "PICK"})

        self.assertFalse(response["success"])
        self.assertEqual(len(fake_socket.payloads), 3)
        self.assertEqual(len(set(fake_socket.payloads)), 1)
        payload = json.loads(fake_socket.payloads[0])
        self.assertEqual(payload["request_id"], "fixed123")

    def test_udp_rejects_numeric_success_field(self):
        communicator = execution.RobotCommunicator(max_retries=1, retry_delay=0)
        communicator.socket = IntegerSuccessSocket()
        communicator._generate_request_id = lambda: "fixed123"

        response = communicator.send_command({"cmd": "PICK"})

        self.assertFalse(response["success"])
        self.assertIn("布尔值", response["message"])


if __name__ == "__main__":
    unittest.main()
