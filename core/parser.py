import re
import json
import requests
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                  "Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://www.douyin.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Cookie": "msToken=abcdefg;",
}


def extract_url(text: str) -> str | None:
    """从分享文本中提取 URL。"""
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None


def resolve_redirect(url: str) -> str:
    """跟随短链重定向，获取真实 URL。"""
    resp = requests.get(url, headers=HEADERS, allow_redirects=False, timeout=15)
    if resp.status_code in (301, 302, 303, 307, 308):
        return resp.headers.get("Location", url)
    return resp.url


def extract_aweme_id(url: str) -> str | None:
    """从 URL 中提取 aweme_id。"""
    # 方式1: URL 路径中包含 /video/数字
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)

    # 方式2: URL 中包含 aweme_id 参数
    match = re.search(r'aweme_id=(\d+)', url)
    if match:
        return match.group(1)

    # 方式3: 从页面内容中提取
    match = re.search(r'/note/(\d+)', url)
    if match:
        return match.group(1)

    return None


def fetch_video_info_from_page(url: str) -> dict | None:
    """尝试从页面 HTML 中提取视频信息。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # 方式1: 查找 _ROUTER_DATA（iesdouyin.com 页面）
        router_match = re.search(
            r'window\._ROUTER_DATA\s*=\s*', html
        )
        if router_match:
            start = router_match.end()
            data_str = _extract_json_object(html, start)
            if data_str:
                result = _extract_from_render_data(data_str)
                if result and result.get("video_url"):
                    return result

        # 方式2: 查找 RENDER_DATA（douyin.com 页面）
        render_match = re.search(
            r'<script id="RENDER_DATA"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if render_match:
            from urllib.parse import unquote
            data_str = unquote(render_match.group(1))
            result = _extract_from_render_data(data_str)
            if result and result.get("video_url"):
                return result

        # 方式3: 直接从 HTML 中查找 playwm URL
        playwm_matches = re.findall(
            r'(https?://[^"\'\\]+playwm[^"\'\\]+)', html
        )
        if playwm_matches:
            video_url = playwm_matches[0].replace("playwm", "play")
            return {"video_url": video_url}

    except Exception:
        pass
    return None


def _extract_json_object(text: str, start: int) -> str | None:
    """从 text[start] 位置提取完整的 JSON 对象。"""
    if start >= len(text) or text[start] != '{':
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == '\\' and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _extract_from_render_data(data_str: str) -> dict | None:
    """从 RENDER_DATA 中提取视频信息。"""
    try:
        data = json.loads(data_str)
        # 递归查找 video 相关数据
        result = _find_video_data(data)
        if result:
            return result
    except (json.JSONDecodeError, Exception):
        pass
    return None


def _find_video_data(obj, depth=0) -> dict | None:
    """递归查找视频播放地址。"""
    if depth > 12:
        return None

    if isinstance(obj, dict):
        # 查找 play_addr（同时尝试提取完整信息）
        if "play_addr" in obj and "video" not in obj:
            play_addr = obj["play_addr"]
            if isinstance(play_addr, dict) and "url_list" in play_addr:
                urls = play_addr["url_list"]
                if urls:
                    video_url = urls[0].replace("playwm", "play")
                    info = {"video_url": video_url}
                    if "desc" in obj:
                        info["title"] = obj["desc"]
                    if "author" in obj and isinstance(obj["author"], dict):
                        info["author"] = obj["author"].get("nickname", "未知作者")
                    return info

        # 包含 video 子对象的完整 aweme 条目
        if "video" in obj and isinstance(obj["video"], dict):
            video = obj["video"]
            play_addr = video.get("play_addr", {})
            if isinstance(play_addr, dict) and "url_list" in play_addr:
                urls = play_addr["url_list"]
                if urls:
                    video_url = urls[0].replace("playwm", "play")
                    info = {"video_url": video_url}
                    if "desc" in obj:
                        info["title"] = obj["desc"]
                    if "author" in obj and isinstance(obj["author"], dict):
                        info["author"] = obj["author"].get("nickname", "未知作者")
                    if "duration" in video:
                        info["duration"] = video["duration"]
                    if "statistics" in obj:
                        info["statistics"] = obj["statistics"]
                    return info

        # 查找 video 对象中的 playApi
        if "playApi" in obj:
            return {"video_url": obj["playApi"]}

        for v in obj.values():
            result = _find_video_data(v, depth + 1)
            if result:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = _find_video_data(item, depth + 1)
            if result:
                return result

    return None


def fetch_video_info_api(aweme_id: str) -> dict | None:
    """通过 API 获取视频信息。"""
    api_url = (
        f"https://www.douyin.com/aweme/v1/web/aweme/detail/"
        f"?aweme_id={aweme_id}"
        f"&aid=6383&cookie_enabled=true&browser_language=zh-CN"
        f"&browser_platform=Win32&browser_name=Chrome&browser_version=120.0.0.0"
    )
    try:
        resp = requests.get(api_url, headers=API_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        aweme_detail = data.get("aweme_detail")
        if not aweme_detail:
            return None

        video = aweme_detail.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])

        if not url_list:
            return None

        video_url = url_list[0].replace("playwm", "play")

        return {
            "video_url": video_url,
            "title": aweme_detail.get("desc", "未知标题"),
            "author": aweme_detail.get("author", {}).get("nickname", "未知作者"),
            "duration": video.get("duration", 0),
        }

    except Exception:
        return None


def parse_douyin_link(share_text: str) -> dict:
    """
    解析抖音分享链接，返回视频信息。

    返回格式:
    {
        "success": True/False,
        "video_url": "无水印视频地址",
        "title": "视频标题",
        "author": "作者",
        "duration": 时长(ms),
        "error": "错误信息（失败时）"
    }
    """
    # 提取 URL
    url = extract_url(share_text.strip())
    if not url:
        return {"success": False, "error": "未找到有效链接，请检查输入"}

    try:
        # 跟随重定向
        real_url = resolve_redirect(url)
        aweme_id = extract_aweme_id(real_url)

        # 方式1: 通过 API 获取
        if aweme_id:
            info = fetch_video_info_api(aweme_id)
            if info and info.get("video_url"):
                info["success"] = True
                return info

        # 方式2: 从页面解析
        info = fetch_video_info_from_page(real_url)
        if info and info.get("video_url"):
            info.setdefault("success", True)
            info.setdefault("title", "未知标题")
            info.setdefault("author", "未知作者")
            return info

        return {"success": False, "error": "无法解析视频地址，链接可能已失效"}

    except requests.Timeout:
        return {"success": False, "error": "请求超时，请检查网络连接"}
    except requests.RequestException as e:
        return {"success": False, "error": f"网络请求失败: {e}"}
    except Exception as e:
        return {"success": False, "error": f"解析失败: {e}"}
