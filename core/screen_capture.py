"""Windows 平台的窗口截图工具。

该模块提供基于 Win32 API 的窗口截图功能，返回 PIL Image 对象。仅在
Windows 平台有效（依赖 win32gui/win32ui/win32con）。

注意:
- 截图要求目标窗口可见且未被完全遮挡；若窗口最小化或被其它窗口遮挡，截图结果
  可能不符合预期。
- 该模块会尝试设置进程为 DPI Aware，以获得正确的像素坐标。
"""

import ctypes
import win32con
import win32gui
import win32ui
from PIL import Image


class ScreenCapture:
    """一个用于按窗口标题截图的简单封装类。

    Attributes:
        window_title: 可选的目标窗口标题（精确匹配）。如果为 None，则后续调用
            `capture_window` 时会因找不到句柄而返回 None。
    """

    def __init__(self, window_title: str | None = None):
        """初始化 ScreenCapture 实例并设置 DPI 感知。

        Args:
            window_title: 目标窗口的精确标题（str）。传 None 表示后续将按 None 查找，
                这种情况下截图会返回 None。


        TODO:
            - 支持通过部分标题或正则匹配窗口
            - 支持最小化/隐藏窗口的截图（例如使用 PrintWindow）
        """
        if window_title is not None and not isinstance(window_title, str):
            raise TypeError("window_title 必须是 str 或 None")

        # 在高 DPI 屏幕上确保坐标和截图尺寸正确
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            # 设置失败时不影响后续逻辑，保守继续执行
            pass

        self.window_title = window_title

    @staticmethod
    def _release_gdi(
        mem_dc: object | None,
        img_dc: object | None,
        hdesktop: int | None,
        desktop_dc: int | None,
        bmp: object | None,
    ) -> None:
        """安全释放 GDI 资源，忽略二次释放等异常。

        Args:
            mem_dc: 内存设备上下文（win32ui.PyCDC）。
            img_dc: 图像设备上下文（win32ui.PyCDC）。
            hdesktop: 桌面窗口句柄。
            desktop_dc: 桌面设备上下文句柄。
            bmp: 位图对象（win32ui.PyCBitmap）。
        """
        for dc in (mem_dc, img_dc):
            if dc is not None:
                try:
                    dc.DeleteDC()
                except Exception:
                    pass
        if hdesktop is not None and desktop_dc is not None:
            try:
                win32gui.ReleaseDC(hdesktop, desktop_dc)
            except Exception:
                pass
        if bmp is not None:
            try:
                win32gui.DeleteObject(bmp.GetHandle())
            except Exception:
                pass

    def capture_window(self) -> Image.Image | None:
        """截取指定窗口的图片并以 PIL Image 返回。

        按 ``self.window_title`` 在系统中查找窗口句柄（FindWindow），
        基于桌面设备上下文进行 BitBlt 拷贝，转换为 RGB 格式的 PIL Image。

        Returns:
            Image.Image | None: 成功时返回 PIL Image；找不到窗口时返回 None。

        Raises:
            RuntimeError: 底层 Win32 API 调用出现不可恢复的错误时抛出。

        Examples:
            >>> sc = ScreenCapture("JJ斗地主")
            >>> img = sc.capture_window()
            >>> isinstance(img, Image.Image) or img is None
            True
        """

        # 1) 查找目标窗口句柄
        hwnd = win32gui.FindWindow(None, self.window_title)
        if not hwnd:
            # 未找到窗口：返回 None（调用方可据此提示用户）
            print(f"没找到窗口: {self.window_title}")
            return None

        # 局部 GDI 对象先初始化为 None，以便在 finally 中安全清理
        hdesktop = None
        desktop_dc = None
        img_dc = None
        mem_dc = None
        bmp = None

        try:
            try:
                # 2) 获取窗口矩形并计算宽高
                left, top, right, bot = win32gui.GetWindowRect(hwnd)
                w = right - left
                h = bot - top

                # 3) 准备设备上下文并执行位块传输
                hdesktop = win32gui.GetDesktopWindow()
                desktop_dc = win32gui.GetWindowDC(hdesktop)
                img_dc = win32ui.CreateDCFromHandle(desktop_dc)
                mem_dc = img_dc.CreateCompatibleDC()

                bmp = win32ui.CreateBitmap()
                bmp.CreateCompatibleBitmap(img_dc, w, h)
                mem_dc.SelectObject(bmp)

                # 将桌面指定区域拷贝到内存位图
                mem_dc.BitBlt((0, 0), (w, h), img_dc, (left, top), win32con.SRCCOPY)

                # 4) 从位图对象读取像素并构建 PIL Image
                bmpinfo = bmp.GetInfo()
                bmpstr = bmp.GetBitmapBits(True)

                # 注意：GetBitmapBits 返回的是 BGRX 格式（每像素 4 字节），PIL 需要转换
                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1)
            finally:
                # 5) 释放 GDI 资源（无论是否异常都会执行）
                self._release_gdi(mem_dc, img_dc, hdesktop, desktop_dc, bmp)
        except Exception as e:
            raise RuntimeError(f"窗口截图失败: {e}") from e

        return img