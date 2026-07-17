"""在可用的 GCC 环境中编译并运行 C 驱动测试。"""

# <!--A-->

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


DRIVER_DIR = pathlib.Path(__file__).resolve().parents[1] / "execution" / "robot_driver"


class RobotDriverBuildTests(unittest.TestCase):
    def test_c_driver_parser_and_idempotency_cache(self):
        gcc = os.environ.get("GCC") or shutil.which("gcc")
        if gcc is None:
            self.skipTest("未在 PATH 或 GCC 环境变量中找到编译器")

        with tempfile.TemporaryDirectory() as temp_dir:
            executable = pathlib.Path(temp_dir) / (
                "robot_driver_test.exe" if os.name == "nt" else "robot_driver_test"
            )
            command = [
                gcc,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "robot_driver_test.c",
                "-lm",
            ]
            if os.name == "nt":
                command.append("-lws2_32")
            command.extend(["-o", str(executable)])

            compile_result = subprocess.run(
                command,
                cwd=DRIVER_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)

            run_result = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertIn("robot_driver tests passed", run_result.stdout)


if __name__ == "__main__":
    unittest.main()
