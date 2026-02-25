from contextlib import redirect_stdout
from io import StringIO, BytesIO
from textwrap import indent
from traceback import format_exc
from inspect import isawaitable

from .. import LOGGER
from ..core.telegram_manager import TgClient
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.telegram_helper.message_utils import send_file, send_message

namespaces = {}


def namespace_of(message):
    if message.chat.id not in namespaces:
        namespaces[message.chat.id] = {
            "__builtins__": globals()["__builtins__"],
            "bot": TgClient.bot,
            "message": message,
            "user": message.from_user or message.sender_chat,
            "chat": message.chat,
        }

    return namespaces[message.chat.id]


def log_input(message):
    LOGGER.info(
        f"IN: {message.text} (user={message.from_user.id if message.from_user else message.sender_chat.id}, chat={message.chat.id})"
    )


async def send(msg, message):
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            await send_file(message, out_file)
    else:
        LOGGER.info(f"OUT: '{msg}'")
        await send_message(message, f"<code>{msg}</code>")


@new_task
async def aioexecute(_, message):
    await send(await do("aexec", message), message)


@new_task
async def execute(_, message):
    await send(await do("exec", message), message)


def cleanup_code(code):
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")


async def do(func, message):
    log_input(message)
    user_id = message.from_user.id if message.from_user else message.sender_chat.id
    if user_id != Config.OWNER_ID:
        return
    content = message.text.split(maxsplit=1)[-1]
    body = cleanup_code(content)
    env = namespace_of(message)

    stdout = StringIO()

    is_exec = False
    compiled_code = None

    try:
        compiled_code = compile(body, "<string>", "eval")
    except SyntaxError:
        pass

    if compiled_code:
        try:
            with redirect_stdout(stdout):
                func_return = await sync_to_async(eval, compiled_code, env)
                if func == "aexec" and isawaitable(func_return):
                    func_return = await func_return
        except:
            value = stdout.getvalue()
            return f"{value}{format_exc()}"
    else:
        is_exec = True
        try:
            if func == "exec":
                exec(f"def func():\n{indent(body, '  ')}", env)
            else:
                exec(f"async def func():\n{indent(body, '  ')}", env)
        except Exception as e:
            return f"{e.__class__.__name__}: {e}"

        rfunc = env["func"]

        try:
            with redirect_stdout(stdout):
                func_return = (
                    await sync_to_async(rfunc) if func == "exec" else await rfunc()
                )
        except:
            value = stdout.getvalue()
            return f"{value}{format_exc()}"

    value = stdout.getvalue()
    result = None

    if func_return is None:
        if value:
            result = f"{value}"
        elif not is_exec:
            result = f"{repr(func_return)}"
    else:
        if not is_exec:
            result = f"{value}{repr(func_return)}"
        else:
            result = f"{value}{func_return}"

    if result:
        return result


@new_task
async def clear(_, message):
    log_input(message)
    user_id = message.from_user.id if message.from_user else message.sender_chat.id
    if user_id != Config.OWNER_ID:
        return
    global namespaces
    if message.chat.id in namespaces:
        del namespaces[message.chat.id]
    await send("Locals Cleared.", message)
