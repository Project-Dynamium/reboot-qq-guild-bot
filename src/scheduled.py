from . import *

# 定时事件
async def scheduled(bot: botpy.Client):
    while True:
        try:
            while bot.is_closed():
                await asyncio.sleep(5)

            # await bot.api.post_message(
            #     content="test",
            #     channel_id="606178450"
            # )
            await asyncio.sleep(30)
        except Exception:
            log.error(traceback.format_exc())
            continue