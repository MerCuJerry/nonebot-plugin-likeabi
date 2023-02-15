import asyncio
import random
import re
from itertools import starmap
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar, cast
from xpinyin import Pinyin

from nonebot import on_command, on_message, get_driver
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State
from typing_extensions import TypeVarTuple, Unpack

from .config import (
    FilterModel,
    MatchModel,
    MessageSegmentModel,
    ReplyModel,
    ReplyType,
    config,
    reload_replies,
    replies,
    DATA_PATH,
)
from nonebot import require
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .db import _sql

T = TypeVar("T")
TArgs = TypeVarTuple("TArgs")

sqlc : _sql

def start_db_connection():
    global sqlc
    sqlc = _sql(DATA_PATH)

def end_db_connection():
    global sqlc
    del sqlc
    
get_driver().on_startup(start_db_connection)
get_driver().on_shutdown(end_db_connection)


def check_list(
    function: Callable[[Unpack[TArgs]], bool],
    will_check: Iterable[tuple[Unpack[TArgs]]],
    is_any: bool = False,
) -> bool:
    # 感谢 nb2 群内 Bryan不可思议 佬的帮助！！
    iterator = starmap(function, will_check)
    return any(iterator) if is_any else all(iterator)


def check_filter(filter: FilterModel[T], val: Optional[T]) -> bool:
    # 都空也算包括
    ok = val in filter.values if val else ((not filter) and (not val))
    if filter.type == "black":
        ok = not ok
    return ok


def check_match(match: MatchModel, event: MessageEvent) -> bool:
    if match.to_me and (not event.is_tome()):
        return False
    
    msg_str = str(event.message)
    msg_plaintext = event.message.extract_plain_text()
    match_template = match.match

    if match.strip:
        msg_str = msg_str.strip()
        msg_plaintext = msg_plaintext.strip()

    if match.type == "regex":
        flag = re.I if match.ignore_case else 0
        return bool(
            (re.search(match_template, msg_str, flag))
            or (
                re.search(match_template, msg_plaintext, flag)
                if match.allow_plaintext
                else False
            )
        )

    if match.ignore_case:
        # regex 匹配已经处理过了，这边不需要管
        msg_str = msg_str.lower()
        match_template = match_template.lower()

    if match.type == "full":
        return (msg_str == match_template) or (
            msg_plaintext == match_template if match.allow_plaintext else False
        )

    # default fuzzy
    if (not msg_str) or (match.allow_plaintext and (not msg_plaintext)):
        return False
    return (match_template in msg_str) or (
        (match_template in msg_plaintext) if match.allow_plaintext else False
    )


async def message_checker(event: MessageEvent, state: T_State) -> bool:
    group = event.group_id if isinstance(event, GroupMessageEvent) else None

    for reply in replies:
        filter_checks = [(reply.groups, group), (reply.users, event.user_id)]
        match_checks = [(x, event) for x in reply.matches]

        if not (
            check_list(check_filter, filter_checks)
            and check_list(check_match, match_checks, True)
        ):
            continue

        state["reply"] = random.choice(reply.replies)
        state["point"] = reply.point
        state["limit"] = reply.limit
        state["ident"] = 'A'+Pinyin().get_pinyin(reply.matches[0].match, '', convert='upper')+'A'
        return True

    return False


def get_reply_msgs(
    reply: ReplyType, refuse_multi: bool = False
) -> Tuple[List[Message], Optional[Tuple[int, int]]]:
    if isinstance(reply, str):
        reply = ReplyModel(type="normal", message=reply)
    elif isinstance(reply, list):
        reply = ReplyModel(type="array", message=reply)

    rt = reply.type
    msg = reply.message
                    
    if rt == "plain":
        return [Message() + cast(str, msg)], None

    if rt == "array":
        return [
            Message(
                [
                    MessageSegment(type=x.type, data=x.data)
                    for x in cast(List[MessageSegmentModel], msg)
                ]
            )
        ], None

    if rt == "multi":
        if refuse_multi:
            raise ValueError("Nested `multi` is not allowed")
        return [
            get_reply_msgs(x, True)[0][0] for x in cast(List[ReplyModel], msg)
        ], reply.delay

    # default normal
    return [Message(cast(str, msg))], None

def likeabi_handle(state: T_State, user_id: str) -> bool:
    if state["limit"] != 0:
        sqlc.sql_insert_update(state["ident"], user_id, 1)
        if int(sqlc.sql_select(state["ident"], user_id)) >= int(state["limit"])+1:
            return False
    
    if state["point"] != 0:
        sqlc.sql_insert_update("LIKEABI", user_id, state["point"])
    
    return True

autoreply_matcher = on_message(
    rule=message_checker,
    block=config.autoreply_block,
    priority=config.autoreply_priority,
)

@autoreply_matcher.handle()
async def _(matcher: Matcher, state: T_State, event: MessageEvent):
    reply: ReplyType = state["reply"]
    if likeabi_handle(state, event.get_user_id()):
        msg, delay = get_reply_msgs(reply)
        for m in msg:
            await matcher.send(m)

            if delay:
                await asyncio.sleep(random.randint(*delay) / 1000)
    else:
        await matcher.finish("今天的回复已经到上限啦")

query = on_command("查询好感度", aliases={"好感度查询"}, priority=98 ,block=True)

@query.handle()
async def queryhandler(matcher: Matcher, event: MessageEvent):
    result = "您的好感度为"+str(sqlc.sql_select("LIKEABI", event.get_user_id()))
    reply = MessageSegment.reply(event.message_id)
    await matcher.finish(reply + result)

reload_matcher = on_command("重载自动回复", permission=SUPERUSER)

@reload_matcher.handle()
async def _(matcher: Matcher):
    try:
        reload_replies()
    except:
        logger.exception("重载配置失败")
        await matcher.finish("重载失败，请检查后台输出")
    else:
        await matcher.finish("重载自动回复配置成功~")
        
async def clear():
    await sqlc.sql_del_other()
    
scheduler.add_job(clear, "cron" , hour="0", minute="0" ,id="Clear")