import psutil
import time
from datetime import timedelta

BOOT = psutil.boot_time()

def get_status() -> str:
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    uptime = timedelta(seconds=int(time.time() - BOOT))
    return (
        f"🖥️ Status\n"
        f"CPU: {cpu}%\n"
        f"RAM: {vm.percent}% ({vm.used//(1024**2)} MB / {vm.total//(1024**2)} MB)\n"
        f"Disk: {disk.percent}% ({disk.used//(1024**3)} GB / {disk.total//(1024**3)} GB)\n"
        f"Uptime: {uptime}\n"
    )
