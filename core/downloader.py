import os
import re
import requests
from pathlib import Path


DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
}


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """清理文件名，移除非法字符。"""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_. ')
    if len(name) > max_len:
        name = name[:max_len].rstrip('_. ')
    return name or "douyin_video"


def get_desktop_path() -> str:
    """获取桌面路径。"""
    if os.name == "nt":
        return str(Path.home() / "Desktop")
    return str(Path.home() / "Desktop")


def download_video(
    video_url: str,
    save_dir: str | None = None,
    filename: str | None = None,
    progress_callback=None,
) -> dict:
    """
    下载视频文件。

    Args:
        video_url: 视频直链地址
        save_dir: 保存目录，默认桌面
        filename: 文件名，默认使用时间戳
        progress_callback: 进度回调函数 callback(downloaded, total)

    Returns:
        {"success": True/False, "path": "文件路径", "error": "错误信息"}
    """
    if not save_dir:
        save_dir = get_desktop_path()

    os.makedirs(save_dir, exist_ok=True)

    if not filename:
        import time
        filename = f"douyin_{int(time.time())}"

    filename = sanitize_filename(filename)
    if not filename.endswith(".mp4"):
        filename += ".mp4"

    filepath = os.path.join(save_dir, filename)

    # 避免覆盖：添加序号
    base, ext = os.path.splitext(filepath)
    counter = 1
    while os.path.exists(filepath):
        filepath = f"{base}_{counter}{ext}"
        counter += 1

    try:
        resp = requests.get(
            video_url,
            headers=DOWNLOAD_HEADERS,
            stream=True,
            timeout=30,
        )
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)

        if progress_callback and total > 0:
            progress_callback(total, total)

        return {
            "success": True,
            "path": filepath,
            "size": downloaded,
        }

    except requests.Timeout:
        return {"success": False, "error": "下载超时，请检查网络"}
    except requests.RequestException as e:
        return {"success": False, "error": f"下载失败: {e}"}
    except OSError as e:
        return {"success": False, "error": f"文件保存失败: {e}"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {e}"}
