# Modification of the module is allowed only if the license is retained.
# MMP""MM""YMM `7MMF'   `7MF' `7MM"""Mq.  7MM"""YMM
# P'   MM   `7   `MA     ,V     MM   `MM.  MM    7
#     MM         VM:   ,V      MM   ,M9   MM   d
#     MM          MM.  M'      MMmmdM9    MMmmMM
#     MM          `MM A'       MM         MM   Y  ,
#     MM           :MM;        MM         MM     ,M
#   .JMML.          VF       .JMML.     .JMMmmmmMMM
#                  ,M
# This module is licensed and fully copyrighted by Type, copyright is allowed while maintaining the author's mention in the code.
# meta developer: @TypeModules

from .. import loader, utils
import asyncio
import re
import logging

logger = logging.getLogger(__name__)

@loader.tds
class TDelMeMod(loader.Module):
    """Удаляет ваши сообщения в чате."""
    strings = {"name": "T:DelMe"}

    def __init__(self):
        self.name = self.strings["name"]

    async def client_ready(self, client, db):
        self.db = db
        self.client = client
        self.autodel_chats = self.db.get("T:DelMe", "autodel_chats", {})
        self.me = await self.client.get_me()

    def _parse_time(self, time_str: str) -> int:
        matches = re.findall(r'(\d+)\s*(h|m|s)', time_str.lower())
        if not matches: return 0
        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 'h': total_seconds += value * 3600
            elif unit == 'm': total_seconds += value * 60
            elif unit == 's': total_seconds += value
        return total_seconds

    async def delmecmd(self, message):
        """Удаляет все ваши сообщения в текущем чате."""
        chat_id = utils.get_chat_id(message)
        msgs_to_del = [message.id]
        async for msg in self.client.iter_messages(chat_id, from_user="me"):
            msgs_to_del.append(msg.id)
        
        for chunk in [msgs_to_del[i:i + 100] for i in range(0, len(msgs_to_del), 100)]:
            await self.client.delete_messages(chat_id, chunk)

    async def delmeautocmd(self, message):
        """Вкл/выкл авто-удаление. Используй: .delmeauto <время> | .delmeauto"""
        chat_id = utils.get_chat_id(message)
        args = utils.get_args_raw(message)

        if not args:
            if chat_id in self.autodel_chats:
                del self.autodel_chats[chat_id]
                self.db.set("T:DelMe", "autodel_chats", self.autodel_chats)
                await utils.answer(message, "<b>[T:DelMe]</b> Авто-удаление в этом чате <u>отключено</u>.")
            else:
                await utils.answer(message, "<b>[T:DelMe]</b> Авто-удаление уже было отключено.\nДля включения укажи время, например: <code>.delmeauto 5m</code>")
            return

        delay = self._parse_time(args)
        if delay <= 0:
            await utils.answer(message, "<b>[T:DelMe]</b> Неверный формат времени.\nПример: <code>1h 30m 5s</code>.")
            return

        self.autodel_chats[chat_id] = delay
        self.db.set("T:DelMe", "autodel_chats", self.autodel_chats)
        await utils.answer(message, f"<b>[T:DelMe]</b> Авто-удаление <u>включено</u> с задержкой <code>{args}</code>.")
    
    async def delmestatuscmd(self, message):
        """Показывает статус автоудаления для чатов."""
        if not self.autodel_chats:
            await utils.answer(message, "<b>[T:DelMe]</b> Нет чатов с включенным автоудалением.")
            return
        
        reply = "<b>[T:DelMe] Активные чаты:</b>\n\n"
        for chat, delay in self.autodel_chats.items():
            reply += f"<b>Чат ID:</b> <code>{chat}</code> | <b>Задержка:</b> <code>{delay}с</code>\n"
        await utils.answer(message, reply)

    async def watcher(self, message):
        if not hasattr(self, "me") or not message or not hasattr(message, "sender_id"):
            return

        if message.text and message.text.startswith(self.get_prefix()):
            return

        chat_id = utils.get_chat_id(message)
        
        if chat_id in self.autodel_chats and message.sender_id == self.me.id:
            delay = self.autodel_chats[chat_id]
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except Exception:
                pass
