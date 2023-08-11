import os, asyncio, time, traceback, random

import botpy
from botpy import logging
from botpy.message import Message, DirectMessage
from botpy.ext.cog_yaml import read

from src.parser import Parser, messageReply
from src.scheduled import scheduled

config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
ENABLE_GUILD = config["enabled_guild_id"]
log = logging.get_logger()

parser = Parser()

ongoing_task = set()
task_queue = asyncio.Queue()
task_status = {}

class Task:
    def __init__(self, id, message, timeout, retry):
        self.id = id
        self.message = message
        self.timeout = timeout
        self.retry = retry


# 机器人主体
class MyClient(botpy.Client):
    async def on_ready(self):
        log.info("Robot is on ready.")
        # 获取除魔术方法外所有 handler 的函数对象
        self.handlers = [getattr(Parser, func) for func in dir(Parser) if func[0] != '_']
        asyncio.gather(bot_info(self), task_supervison(self))

    # 频道
    async def on_at_message_create(self, message: Message):
        print(f"Receive {message.content} from guild {message.author.username}")
        if message.guild_id not in ENABLE_GUILD:
            return
        await command_handler(self, message)
    
    # 私信
    async def on_direct_message_create(self, message: DirectMessage):
        print(f"Receive {message.content} from DM {message.author.username}")
        await command_handler(self, message)
    

async def command_handler(bot: MyClient, message, timeout = config["task_timeout"], retry = 0):
    if retry > config["retry_count"]:
        await messageReply("错误：该命令超时次数过多，已终止运行。请等待几分钟后再尝试执行命令", bot.api, message)
        return

    start_time = time.time()
    task_id = int(time.time()*1000) + random.randint(0, 1000)
    task_status[task_id] = 0
    await task_queue.put(Task(task_id, message, timeout, retry))
    for handler in bot.handlers:
        try:
            if await handler(api=bot.api, message=message):
                log.info(f"Task done: {time.time() - start_time}s - {message.content} from {message.author.username}")
                break
        except asyncio.TimeoutError:
            log.warning(f"Timeout when dealing the task ({retry}): {message.content} from {message.author.username}")
            return

    task_status[task_id] = 1

# 处理因为超时而没有完成的任务
async def task_supervison(bot: MyClient):
    while True:
        task: Task = await task_queue.get()
        
        async def re_handle(task: Task):
            await asyncio.sleep(task.timeout + 5)
            if task_status.pop(task.id, 1) != 1:
                print(f"Retrying {task.retry + 1} time : {task.message.content} from {task.message.author.username}")
                await command_handler(bot, task.message, task.timeout * 1.25, task.retry + 1)
        
        async_task = asyncio.create_task(re_handle(task))
        ongoing_task.add(async_task)
        async_task.add_done_callback(ongoing_task.discard)
        await asyncio.sleep(0)


# 查询机器人相关信息
async def bot_info(bot: MyClient):
    log.info('- Bot guild info:')
    guild_list = await bot.api.me_guilds()
    for guild in guild_list:
        log.info(f'| guild_id: {guild.get("id")} guild_name: {guild.get("name")}')
    
    log.info('- Enabled guild info:')
    for enabled_guild in ENABLE_GUILD:
        log.info(f'· Guild id: {enabled_guild}')
        for channel in (await bot.api.get_channels(guild_id=enabled_guild)):
            log.info(f'| channel_id: {channel.get("id")} channel_name: {channel.get("name")}')


# 启动机器人和相关服务
async def main():
    client = MyClient(intents=botpy.Intents.all())
    async with client as c:
        await asyncio.gather(
            c.start(appid=config["appid"], token=config["token"]),
            scheduled(c)
        )


if __name__ == "__main__":
    # 我也不想在这里整个 while True ，但是这个 api 实在是太容易超时了，库还不接住自己的错误
    while True:
        try:
            asyncio.run(main())
        except Exception:
            log.error(traceback.format_exc())
            if config["restart_time"] != 0:
                log.info(f"Will be restart in {config['restart_time']}s")
                time.sleep(config["restart_time"])
                continue

        exit(0)
