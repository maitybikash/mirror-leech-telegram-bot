from ast import literal_eval
from httpx import AsyncClient
from asyncio.subprocess import PIPE
from functools import partial, wraps
from concurrent.futures import ThreadPoolExecutor
from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    run_coroutine_threadsafe,
    sleep,
)

from ... import user_data, bot_loop
from ...core.config_manager import Config
from ..telegram_helper.button_build import ButtonMaker
from .telegraph_helper import telegraph
from .help_messages import (
    YT_HELP_DICT,
    MIRROR_HELP_DICT,
    CLONE_HELP_DICT,
)

COMMAND_USAGE = {}

THREAD_POOL = ThreadPoolExecutor(max_workers=500)


class SetInterval:
    def __init__(self, interval, action, *args, **kwargs):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self._set_interval(*args, **kwargs))

    async def _set_interval(self, *args, **kwargs):
        while True:
            await sleep(self.interval)
            await self.action(*args, **kwargs)

    def cancel(self):
        self.task.cancel()


def _build_command_usage(help_dict, command_key):
    buttons = ButtonMaker()
    for name in list(help_dict.keys())[1:]:
        buttons.data_button(name, f"help {command_key} {name}")
    buttons.data_button("Close", "help close")
    COMMAND_USAGE[command_key] = [help_dict["main"], buttons.build_menu(3)]
    buttons.reset()


def create_help_buttons():
    _build_command_usage(MIRROR_HELP_DICT, "mirror")
    _build_command_usage(YT_HELP_DICT, "yt")
    _build_command_usage(CLONE_HELP_DICT, "clone")


def bt_selection_buttons(id_):
    gid = id_[:12] if len(id_) > 25 else id_
    pin = Config.get_pin(id_)
    buttons = ButtonMaker()
    if Config.WEB_PINCODE:
        buttons.url_button("Select Files", f"{Config.BASE_URL}/app/files?gid={id_}")
        buttons.data_button("Pincode", f"sel pin {gid} {pin}")
    else:
        buttons.url_button(
            "Select Files", f"{Config.BASE_URL}/app/files?gid={id_}&pin={pin}"
        )
    buttons.data_button("Done Selecting", f"sel done {gid} {id_}")
    buttons.data_button("Cancel", f"sel cancel {gid}")
    return buttons.build_menu(2)


async def get_telegraph_list(telegraph_content):
    path = [
        (
            await telegraph.create_page(
                title="Mirror-Leech-Bot Drive Search", content=content
            )
        )["path"]
        for content in telegraph_content
    ]
    if len(path) > 1:
        await telegraph.edit_telegraph(path, telegraph_content)
    buttons = ButtonMaker()
    buttons.url_button("🔎 VIEW", f"https://telegra.ph/{path[0]}")
    return buttons.build_menu(1)


def arg_parser(items, arg_base):
    if not items:
        return

    # Flags that are strictly boolean (never consume value)
    pure_bool = {
        "-s",
        "-j",
        "-f",
        "-fd",
        "-fu",
        "-sync",
        "-hl",
        "-doc",
        "-med",
        "-ut",
        "-bt",
    }

    # Flags that can be boolean (if no value provided) or take a value
    hybrid_bool = {
        "-b",
        "-e",
        "-z",
        "-d",
        "-sv",
        "-ss",
    }

    i = 0
    total = len(items)
    arg_start = -1

    while i < total:
        part = items[i]

        if part in arg_base:
            if arg_start == -1:
                arg_start = i

            # Case 1: Pure boolean flag
            if part in pure_bool:
                arg_base[part] = True
                i += 1
                continue

            # Case 2: Hybrid flag acting as boolean
            # It acts as boolean if it's the last item OR the next item is a recognized flag
            is_next_flag = False
            if i + 1 < total:
                next_item = items[i + 1]
                if next_item in arg_base:
                    # Exception: -c allows -c as value
                    if not (part == "-c" and next_item == "-c"):
                        is_next_flag = True

            if part in hybrid_bool and (i + 1 == total or is_next_flag):
                arg_base[part] = True
                i += 1
                continue

            # Case 3: Flag consuming value(s)
            sub_list = []
            j = i + 1
            while j < total:
                item = items[j]
                if item in arg_base:
                    # Check for -c exception
                    if part == "-c" and item == "-c":
                        sub_list.append(item)
                        j += 1
                        continue

                    # Check if we should stop consuming
                    if part == "-ff":
                        check = " ".join(sub_list).strip()
                        # If inside brackets, continue consuming flags
                        if check.startswith("[") and not check.endswith("]"):
                            sub_list.append(item)
                            j += 1
                            continue

                    # If we are here, it's a new flag and we should stop consuming
                    break

                sub_list.append(item)
                j += 1

            if sub_list:
                value = " ".join(sub_list)
                if part == "-ff":
                    # Handle -ff specially for tuple/list evaluation
                    if value.strip().startswith("["):
                        try:
                            arg_base[part].add(tuple(literal_eval(value)))
                        except Exception:
                            pass
                    else:
                        arg_base[part].add(value)
                else:
                    arg_base[part] = value

                i = j
            else:
                # No value consumed. If it was hybrid, we handled it above.
                # If it was a standard value flag (like -n), it remains default.
                i += 1

        else:
            # Not in arg_base.
            i += 1

    if "link" in arg_base:
        link_items = items[:arg_start] if arg_start != -1 else items
        if link_items:
            arg_base["link"] = " ".join(link_items)


def get_size_bytes(size):
    size = size.lower()
    if "k" in size:
        size = int(float(size.split("k")[0]) * 1024)
    elif "m" in size:
        size = int(float(size.split("m")[0]) * 1048576)
    elif "g" in size:
        size = int(float(size.split("g")[0]) * 1073741824)
    elif "t" in size:
        size = int(float(size.split("t")[0]) * 1099511627776)
    else:
        size = 0
    return size


async def get_content_type(url):
    try:
        async with AsyncClient() as client:
            response = await client.get(url, allow_redirects=True, verify=False)
            return response.headers.get("Content-Type")
    except:
        return None


def update_user_ldata(id_, key, value):
    user_data.setdefault(id_, {})
    user_data[id_][key] = value


async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    try:
        stdout = stdout.decode().strip()
    except:
        stdout = "Unable to decode the response!"
    try:
        stderr = stderr.decode().strip()
    except:
        stderr = "Unable to decode the error!"
    return stdout, stderr, proc.returncode


def new_task(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        task = bot_loop.create_task(func(*args, **kwargs))
        return task

    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREAD_POOL, pfunc)
    return await future if wait else future


def async_to_sync(func, *args, wait=True, **kwargs):
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def loop_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future

    return wrapper
