#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import urllib.request


def download_file(url, save_path):
    print(f"📥 正在下载: {url}")
    print(f"📁 保存到: {save_path}")
    try:
        urllib.request.urlretrieve(url, save_path, reporthook=progress_hook)
        print("\n✅ 下载完成")
        return True
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        return False


def progress_hook(count, block_size, total_size):
    if total_size <= 0:
        return
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write(f"\r进度: {percent}%")
    sys.stdout.flush()


def extract_zip(zip_path, extract_dir):
    print(f"📦 正在解压: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("✅ 解压完成")
        return True
    except Exception as e:
        print(f"❌ 解压失败: {e}")
        return False


def main():
    model_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(model_dir, exist_ok=True)

    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
    zip_path = os.path.join(model_dir, "vosk-model-small-cn-0.22.zip")
    extract_path = os.path.join(model_dir, "vosk-model-small-cn-0.22")

    if os.path.exists(extract_path):
        print(f"✅ 模型已存在: {extract_path}")
        return

    if not download_file(model_url, zip_path):
        sys.exit(1)

    if not extract_zip(zip_path, model_dir):
        sys.exit(1)

    os.remove(zip_path)
    print(f"🗑️ 已删除临时文件: {zip_path}")

    print(f"\n🎉 Vosk 模型下载完成！")
    print(f"📁 模型位置: {extract_path}")


if __name__ == "__main__":
    main()