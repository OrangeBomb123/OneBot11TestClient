import os
import subprocess
import sys

# 检查并安装依赖
def install_dependencies():
    print("正在检查依赖...")
    try:
        # 尝试导入websockets，如果失败则安装
        import websockets
        import psutil
        import requests
        import PIL
        print("依赖已安装，正在启动程序...")
    except ImportError:
        print("正在安装依赖...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            print("依赖安装成功！")
        except Exception as e:
            print(f"安装依赖失败: {e}")
            print("请手动运行: pip install -r requirements.txt")
            input("按回车键退出...")
            sys.exit(1)

# 启动主程序
def start_app():
    try:
        subprocess.run([sys.executable, 'onebot_client.py'])
    except Exception as e:
        print(f"启动程序失败: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    install_dependencies()
    start_app()