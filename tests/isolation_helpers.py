import os
import threading
import time


def return_value(value):
    return value


def raise_error():
    raise ValueError("worker boom")


def hang_forever():
    while True:
        time.sleep(1)


def exit_without_result():
    os._exit(7)


def return_with_hanging_thread():
    threading.Thread(target=time.sleep, args=(60,)).start()
    return {"ok": True}
