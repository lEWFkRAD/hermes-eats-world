import os
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
