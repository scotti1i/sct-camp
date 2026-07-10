"""camp-workbench:工具要界面,就用这个壳,别再手搓 http.server。

用法:
    from camp_workbench import Workbench
    wb = Workbench("Week 5 · 邮件工作台")
    @wb.route("/")
    def home(query):
        return "<p>你好</p>"           # 返回 HTML 片段,壳负责包页面
    wb.serve(port=8785)

历史上三个项目各写了一套本地 server + 三种界面长相,收敛到此为止。
"""

from camp_workbench.server import Workbench, button

__all__ = ["Workbench", "button"]
