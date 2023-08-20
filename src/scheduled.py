from . import *

import math, httpx
from lxml import etree

async def essay_generate(text: str):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    params = { 
        '谓语': '取得',
        '宾语': '丨',
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('https://zuowen.jackjyq.com/', params=params,  headers=headers)
            html = etree.HTML(response.text,etree.HTMLParser())
            essay = html.xpath("/html/head/meta[3]/@content")[0]
        
        return essay[8:].replace("丨", text) + "\n"
    except:
        return "\n"

async def announcement(bot: botpy.Client):
    async for task in db.database["GuildTask"].find({"taskType": "announce_R"}):
        info = task["taskDetails"]
        date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info["scoreRecord"]["createTime"]))

        r_range = math.floor(info["R"]/1000)
        in_range_count =  await db.database["User"].count_documents(
            {"gameInfo.userR": {"$gte": r_range * 1000, "$lt": (r_range + 1) * 1000}}
        )
        above_count =  await db.database["User"].count_documents(
            {"gameInfo.userR": {"$gte": r_range * 1000}}
        )

        congrate = f"恭喜玩家 {info['username']} 在 {date} 于 {info['setName']} 中获得了单曲 {info['scoreRecord']['R']}R 的成绩，个人 R 值达到了 {info['R']} 点。"
        essay = await essay_generate(str(r_range * 1000))
        stat = f"目前，共有 {in_range_count} 名玩家的 R 值在 {r_range * 1000} - {(r_range + 1) * 1000} ，共有 {above_count} 名玩家的 R 值超过了 {r_range * 1000} 。"

        await asyncio.gather(
            await bot.api.post_message(
                content=f"{congrate}{essay}{stat}",
                channel_id=config["announced_channel_id"]
            ),
            await db.delete("GuildTask", id = task["_id"])
        )

async def fill_guild_username(bot: botpy.Client):
    async for u in db.database["GuildBind"].find():
        try:
            user_info = (await bot.api.get_guild_member(
                guild_id=config["enabled_guild_id"][0],
                user_id=u["guildUserId"]
            ))["user"]
            u["guildUsername"] = user_info['username']
            u["guildAvatar"] = user_info['avatar']
            await db.update("GuildBind", u, id = u["_id"])
        except Exception:
            traceback.print_exc()
            log.error(traceback.format_exc())
            continue

# 周期事件
async def scheduled(bot: botpy.Client):
    while True:
        try:
            while bot.is_closed():
                await asyncio.sleep(5)
            
            asyncio.gather(
                announcement(bot),
                fill_guild_username(bot)
            )
            
            await asyncio.sleep(30)
        except ServerError:
            await asyncio.sleep(3600)
        except Exception:
            log.error(traceback.format_exc())
            continue
