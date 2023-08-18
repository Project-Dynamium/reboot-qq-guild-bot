from . import *
from functools import wraps
import hashlib, datetime, textwrap

from .curve import make_curve
from .img_generator import img_task


# 通用消息回复
async def messageReply(content: str, api: BotAPI, message: Msg, recall_time: int = -1, **kwargs):
    if isinstance(message, Message):
        kwargs.setdefault("message_reference", Reference(message_id=message.id))
        kwargs.setdefault("channel_id", message.channel_id)
        post_func = api.post_message
    elif isinstance(message, DirectMessage):
        kwargs.setdefault("guild_id", message.guild_id)
        post_func = api.post_dms

    message_reply = await post_func(
        content=content,
        msg_id=message.id,
        **kwargs
    )

    if recall_time == -1 or isinstance(message, DirectMessage):
        return
    await asyncio.sleep(recall_time)
    # Recall reply message
    # await api.recall_message(message.channel_id, message_reply.get("id"), hidetip=True)
    # Recall command message
    # await api.recall_message(message.channel_id, message.id, hidetip=True)

# 限定消息来源
def messageSource(msgType):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            message = kwargs["message"]
            api = kwargs["api"]
            if isinstance(message, msgType):
                return await func(*args, **kwargs)

            if msgType == DirectMessage:
                await messageReply("此功能仅限私聊内使用", api, message, recall_time=5)
            elif msgType == Message:
                await messageReply("此功能仅限频道内使用", api, message, recall_time=5)
            return

        return wrapper
    return decorator

# 检查账号绑定情况
def ensureUserBind(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        message = kwargs["message"]
        api = kwargs["api"]
        doc = await db.find("GuildBind", {"guildUserId": message.author.id})
        if doc is None:
            await messageReply("请先私聊使用 /bind 绑定游戏账号", api, message, recall_time=5)
            return
        return await func(uid=doc["gameUserId"], *args, **kwargs)

    return wrapper

# 通用未知异常捕获
def captureException(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result if result is not None else True
        except ServerError:
            traceback.print_exc()
        except Exception as e:
            message = kwargs["message"]
            api = kwargs["api"]
            log.error(traceback.format_exc())
            err_str = repr(e) if e in repr(e) else f"{repr(e)} {e}"
            await messageReply(f"机器人运行时遇到未知错误，请向管理反馈以下错误信息：\n{err_str}", api, message)
            return

    return wrapper

# 发送表情
def sendEmojiReaction(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        message = kwargs["message"]
        api = kwargs["api"]
        if isinstance(message, Message):
            await api.put_reaction(
                message_id=message.id,
                channel_id=message.channel_id,
                emoji_id="128076",
                emoji_type=2
            )
            await func(*args, **kwargs)
            # May reach api rate limit so disabled it
            # await api.delete_reaction(
            #     message_id=message.id,
            #     channel_id=message.channel_id,
            #     emoji_id="128076",
            #     emoji_type=2
            # )
        else:
            await func(*args, **kwargs)

    return wrapper


class Parser:
    # 游戏内容相关
    @Commands(("/hdb", "/recent"))
    @captureException
    @ensureUserBind
    @sendEmojiReaction
    async def GenerateBest20Score(uid, api: BotAPI, message: Msg, **kwargs):
        args = [arg for arg in message.content.strip().split() if arg[:3] != '<@!']
        task_type = (args[0] == "/recent")
        username = " ".join(args[1:])

        if username == "":
            doc = await db.find("GuildBind", {"guildUserId": message.author.id})
            if doc is None:
                await messageReply("请先私聊使用 /bind 绑定游戏账号", api, message, recall_time=5)
                return
            
            user_profile = await db.find("User", id = doc["gameUserId"])
        else:
            user_profile = await db.find("User", {"username": username})
            if user_profile is None:
                await messageReply("错误：该玩家不存在", api, message, recall_time=5)
                return

        if task_type == 0 and len(user_profile["gamePlay"]["rankAccuracy"]) < 1:
            await messageReply(f"错误：{'该玩家' if username != '' else '你'}没有 Rank 成绩", api, message, recall_time=5)
        if task_type == 1 and len(user_profile["gamePlay"]["recentPlay"]) < 1:
            await messageReply(f"错误：{'该玩家' if username != '' else '你'}最近并没有游玩歌曲", api, message, recall_time=5)

        img = await img_task(user_profile, task_type)
        await messageReply(f"<@!{message.author.id}>" if isinstance(message, Message) else None
            , api, message, file_image=img, message_reference=None)


    @Commands("/curve")
    @captureException
    @sendEmojiReaction
    async def GenerateTimeCurve(api: BotAPI, message: Msg, **kwargs):
        args = [arg for arg in message.content.strip().split() if arg[:3] != '<@!']
        if len(args) < 2:
            await messageReply('错误：参数输入不正确。\n此命令使用方法（省略用户名则查询自己）：\n/curve 用户名 (第n天前,结束日期)', api, message, recall_time=5)
            return

        cmd = " ".join(args[1:])
        username = cmd[:cmd.rfind("(") - 1]

        try:
            get_daystamp = lambda x: int((int(x) + 28800) / 86400)
            time_pair = cmd[cmd.rfind("(") + 1 : cmd.rfind(")")].split(",")
            if len(time_pair) == 1:
                time_pair.append(datetime.datetime.now().strftime("%Y-%m-%d"))

            end_time = min(
                get_daystamp(time.mktime(time.strptime(time_pair[1], "%Y-%m-%d"))),
                get_daystamp(time.time())
            )
            time_span = int(time_pair[0])
        except Exception:
            await messageReply('错误：无效的时间。参考样例：(60,2023-1-1) (120)\n注意，请确保符号都为英文符号', api, message, recall_time=5)
            traceback.print_exc()
            return

        #print(cmd, username)
        if f"{username})" == cmd:   # 未指定用户名
            doc = await db.find("GuildBind", {"guildUserId": message.author.id})
            if doc is None:
                await messageReply("请先私聊使用 /bind 绑定游戏账号", api, message, recall_time=5)
                return
            user_profile = await db.find("User", id = doc["gameUserId"])
        else:
            user_profile = await db.find("User", {"username": username})

        if user_profile is None:
            await messageReply(f'错误：用户`{username}`不存在', api, message, recall_time=5)
            return

        try:
            available_till = min(int(d) for d in user_profile["gameInfo"]["RUpdate"].keys()) + 1
            time_span = min(time_span, end_time-available_till)
            if time_span < 2:
                await messageReply('错误：所选时间段范围过小', api, message, recall_time=5)
                return
        except Exception:
            await messageReply('错误：该用户可能没有游玩记录或游玩时间过短', api, message, recall_time=5)
            traceback.print_exc()
            return

        img = await make_curve(user_profile, time_span, end_time, available_till)
        await messageReply(f"<@!{message.author.id}>" if isinstance(message, Message) else None
                , api, message, file_image=img, message_reference=None)


    @Commands("/calc")
    @captureException
    async def CalculateR(api: BotAPI, message: Msg, **kwargs):
        args = [arg for arg in message.content.strip().split() if arg[:3] != '<@!']
        try:
            assert float(args[-1]) <= 100 and float(args[-1]) >= 0
            calc_R = lambda acc, rValue : max(int(acc * 50), int(acc ** 8 * rValue ** 3 - rValue ** 2.8))

            if len(args) == 3:
                assert float(args[1]) <= 100 and float(args[1]) >= 0
                res = calc_R(float(args[1])/100, float(args[2]))
                await messageReply(f"R({round(float(args[1]),2)}%, {args[-1]})={res}", api, message)
            elif len(args) == 5:
                acc = (int(args[1])*2+int(args[2])) / \
                    float((int(args[1]) + int(args[2]) + int(args[3]))*2)
                res = calc_R(acc, float(args[4]))
                await messageReply(f"R({round(acc*100,2)}%, {args[-1]})={res}", api, message)
            else:
                await messageReply("错误：参数输入不正确，请依次输入`P-G-M-定数`或`ACC-定数`", api, message, recall_time=5)
        except Exception:
            await messageReply("错误：不合法的输入，请检查输入是否正确", api, message, recall_time=5)


    # 用户相关
    @Commands("/bind")
    @captureException
    @messageSource(DirectMessage)
    async def UserBind(api: BotAPI, message: DirectMessage, **kwargs):
        gid = message.author.id
        if (await db.find("GuildBind", {"guildUserId": gid})) is not None:
            await messageReply("错误：你已经绑定过游戏账号", api, message)
            return
        
        task_token = hashlib.md5(f"{gid}{time.time()}&sA1t".encode()).hexdigest()
        await db.delete("GuildTask", {"taskType": "bindguild", "taskDetails.guildId": gid})
        await db.insert("GuildTask", 
            {
                "taskType": "bindguild",
                "taskDetails":{"guildId": gid, "token": task_token, "expireTime": int(time.time()+60*5)}
            })
        await messageReply(f"请在游戏内的商店搜索栏中输入以下命令完成账号绑定，有效期五分钟\n\n.bind guild {task_token}", api, message)
        return


    @Commands("/reg")
    @captureException
    @messageSource(DirectMessage)
    async def UserRegister(api: BotAPI, message: DirectMessage, **kwargs):
        username = " ".join(message.content.strip().split()[1:])
        gid = message.author.id

        if username == "":
            await messageReply("错误：请输入你要使用的用户名", api, message)
            return
        if len(username) < 2 or len(username) > 20:
            await messageReply("错误：用户名过短或过长，请重新输入", api, message)
            return
        if (await db.find("GuildBind", {"guildUserId": gid})) is not None:
            await messageReply("错误：你已经注册过游戏账号", api, message)
            return

        doc = await db.find("GuildTask", {"taskType": "reg", "taskDetails.guildId": gid})
        if doc is None:
            if (await db.find("User", {"username": username})) is not None or \
                        (await db.find("GuildTask", {"taskDetails.gameUsername": username})) is not None:
                await messageReply(f"错误：用户名`{username}`已被注册", api, message)
                return
            await db.insert("GuildTask", 
                {
                    "taskType": "reg",
                    "taskDetails":{"guildId": gid, "gameUsername": username, "expireTime": int(time.time()+60*5)}
                })

            await messageReply(f"你要注册的游戏账户名为：{username}\n请在五分钟内再次输入同样的命令确定注册", api, message)
        else:
            await db.delete("GuildTask", id = doc["_id"])
            if doc["taskDetails"]["expireTime"] < int(time.time()):
                await messageReply("错误：注册超时，请重新注册", api, message)
                return
            if doc["taskDetails"]["gameUsername"] != username:
                await messageReply("错误：两次输入的游戏账户名不一致，请重新注册", api, message)
                return

            game_doc = await db.find("User", {"username": ""})
            game_doc["_id"] = ObjectId()
            game_doc["username"] = username
            game_doc["accountStatus"]["accountCreateTime"] = int(time.time())
            asyncio.gather(
                db.insert("GuildBind", {"guildUserId": gid, 
                                        "guildUsername": message.author.username, 
                                        "gameUserId": game_doc["_id"],
                                        "gameUsername": username}),
                db.insert("User", game_doc, specific_id = True)
            )
            await messageReply(f"注册成功，你的游戏账户名为：{username}\n账号已自动绑定频道机器人，请使用 /reset 命令设置账号密码", api, message)

        return


    @Commands("/reset")
    @captureException
    @messageSource(DirectMessage)
    @ensureUserBind
    async def UserPasswordReset(uid, api: BotAPI, message: DirectMessage, **kwargs):
        password = " ".join(message.content.strip().split()[1:])
        gid = message.author.id

        if password == "":
            await messageReply("错误：请输入新密码", api, message)
            return
        if len(password) < 5 or len(password) > 20:
            await messageReply("密码过短或过长，请重新输入", api, message)
            return

        doc = await db.find("GuildTask", {"taskType": "pwd", "taskDetails.guildId": gid})
        if doc is None:
            await db.insert("GuildTask", 
                {
                    "taskType": "pwd",
                    "taskDetails":{"guildId": gid, "password": hashlib.sha256(password.encode()).hexdigest()
                                   , "expireTime": int(time.time()+60*5)}
                })
            await messageReply("你现在正在重置密码，请在五分钟内再次输入同样的命令确定重置密码", api, message)
        else:
            await db.delete("GuildTask", id = doc["_id"])
            if doc["taskDetails"]["expireTime"] < int(time.time()):
                await messageReply("错误：重置密码超时，请重新重置", api, message)
                return
            if doc["taskDetails"]["password"] != hashlib.sha256(password.encode()).hexdigest():
                await messageReply("错误：两次输入的密码不一致，请重新重置", api, message)
                return

            game_doc = await db.find("User", id = uid)
            game_doc["password"] = doc["taskDetails"]["password"]
            await db.update("User", game_doc, id = uid)
            await messageReply("密码重置成功，请牢记密码", api, message)

        return
    

    @Commands("/help")
    @captureException
    @messageSource(DirectMessage)
    async def UserHelp(api: BotAPI, message: DirectMessage, **kwargs):
        help_msg = textwrap.dedent("""
            -- Hinix 频道机器人使用帮助 --
            注意事项：在频道输入/自动联想命令，所有在频道内的命令都需要@机器人使用，私聊不需要。
            请确保命令中所有符号都为英文符号，部分命令仅限私聊使用。
            只要使用了命令，不管命令是否成功执行，机器人*都会回复*至少一条消息，如果机器人没有回复请检查是否使用了不支持的命令。
            如果确定使用了正确的命令，机器人长时间仍然没有回复，请尝试重新执行命令。
            
            命令参数和部分解释：
            /hdb 用户名  |  用户名可省略
            
            /calc Perfect数 Good数 Miss数 谱面定数
            /calc ACC值 谱面定数  |  ACC值不需要加百分号
            
            /recent 用户名  |  用户名可省略
            
            /curve 用户名 (第n天前)  |  用户名可省略
            /curve 用户名 (第n天前,截止日期)  |  用户名可省略，日期格式应形如2023-01-01
            
            /bind  |  将频道账号与游戏账号绑定
            
            /reg 用户名 |  注册游戏账号
            
            /reset 密码 |  重置游戏密码              
        """[1:])
        await messageReply(help_msg, api, message)
        return
    
    @Commands("/dm")
    @captureException
    @messageSource(Message)
    async def InitiativeDM(api: BotAPI, message: DirectMessage, **kwargs):
        dm_session = await api.create_dms(
            guild_id = message.guild_id,
            user_id = message.author.id
        )
        return await api.post_dms(
            content = "由机器人主动发送一条消息，现在你可以继续使用私聊了。",
            guild_id = dm_session.get("guild_id")
        )
        