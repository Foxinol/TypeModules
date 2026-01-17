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
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.types import InputFolderPeer
import random
import logging
import asyncio

logger = logging.getLogger(__name__)


@loader.tds
class THentaiModule(loader.Module):
    """Сборник хентая в одном месте, без смс и регистрации маминой карточки на сторонних сайтах скачать"""

    strings = {"name": "T:Hentai"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "bind_enabled",
                False,
                "Enable/disable trigger word feature",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "bind_word",
                "хентай",
                "Word that triggers random media send",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "bind_chat_id",
                0,
                "Chat ID where trigger word will work (0 = disabled)",
                validator=loader.validators.Integer()
            ),
            loader.ConfigValue(
                "delay_seconds",
                0,
                "Delay in seconds before sending media (0 = no delay)",
                validator=loader.validators.Integer(minimum=0, maximum=300)
            )
        )
        self._source_channels = [
            "mirhentaya",
            "TheSafeAnnaAnon",
            "joinchat/AAAAAFaIBD7CuB8_dbcMvw",
            "joinchat/AAAAAFZTTF99JzOWLZH74A"
        ]
        self._required_chat = "FHeta_Chat"
        self._dev_channel = "adaptype"

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        
        try:
            try:
                await self._client(JoinChannelRequest(f"@{self._dev_channel}"))
            except Exception:
                pass
            
            dev_entity = await self._client.get_entity(f"@{self._dev_channel}")
            await self._archive_chat(dev_entity)
        except Exception:
            pass

        for channel in self._source_channels:
            try:
                if channel.startswith("joinchat/"):
                    invite_link = f"https://t.me/{channel}"
                    await self._client(JoinChannelRequest(invite_link))
                    entity = await self._client.get_entity(invite_link)
                else:
                    await self._client(JoinChannelRequest(f"@{channel}"))
                    entity = await self._client.get_entity(f"@{channel}")
                await self._archive_chat(entity)
            except Exception:
                pass

    async def _archive_chat(self, entity):
        """Archive a chat/channel"""
        try:
            await self._client(EditPeerFoldersRequest(
                folder_peers=[
                    InputFolderPeer(peer=entity, folder_id=1)
                ]
            ))
        except Exception:
            pass

    async def _check_membership(self, message):
        """Check if user is member of required chat"""
        try:
            chat = await self._client.get_entity(f"@{self._required_chat}")
            await self._client.get_permissions(chat, "me")
            return True
        except Exception:
            pass
        
        await self._client.send_message(
            message.chat_id,
            f"❌ <b>Вы не состоите в чате @{self._required_chat}</b>\n\n"
            f"<i>Для использования модуля необходимо вступить в чат спонсора</i>",
            buttons=[
                [{"text": "🚀 Зайти в чат", "url": f"https://t.me/{self._required_chat}"}]
            ],
            reply_to=message.id
        )
        await message.delete()
        return False

    async def _get_random_media(self, media_type="all"):
        """Get random media from source channels"""
        all_media = []
        
        for channel in self._source_channels:
            try:
                if channel.startswith("joinchat/"):
                    entity = await self._client.get_entity(f"https://t.me/{channel}")
                else:
                    entity = await self._client.get_entity(f"@{channel}")
                
                async for msg in self._client.iter_messages(entity, limit=50):
                    if msg.media:
                        if media_type == "video" and msg.video:
                            all_media.append(msg)
                        elif media_type == "photo" and msg.photo:
                            all_media.append(msg)
                        elif media_type == "all" and (msg.video or msg.photo):
                            all_media.append(msg)
            except Exception as e:
                logger.debug(f"Error fetching from {channel}: {e}")
                continue
        
        if all_media:
            return random.choice(all_media)
        return None

    async def _send_media(self, message, media_type):
        """Send random media"""
        if not await self._check_membership(message):
            return

        await utils.answer(message, "🔍 <b>Ищу медиа...</b>")
        
        media_msg = await self._get_random_media(media_type)
        
        if not media_msg:
            await utils.answer(message, "❌ <b>Медиа не найдено!</b>")
            return
        
        try:
            await self._client.send_file(
                message.chat_id,
                media_msg.media,
                supports_streaming=True
            )
            await message.delete()
        except Exception as e:
            await utils.answer(message, f"❌ <b>Ошибка:</b> {e}")

    @loader.command(ru_doc="Получить случайное видео")
    async def vidfcmd(self, message):
        """Get random video"""
        await self._send_media(message, "video")

    @loader.command(ru_doc="Получить случайную картинку")
    async def imfcmd(self, message):
        """Get random image"""
        await self._send_media(message, "photo")

    @loader.watcher()
    async def watcher(self, message):
        """Watch for trigger word in messages"""
        if not self.config["bind_enabled"]:
            return
        
        if not self.config["bind_word"] or not self.config["bind_chat_id"]:
            return
        
        if not hasattr(message, "text") or not message.text or message.out:
            return
        
        if utils.get_chat_id(message) != self.config["bind_chat_id"]:
            return
        
        if self.config["bind_word"].lower() not in message.text.lower():
            return
        
        try:
            chat = await self._client.get_entity(f"@{self._required_chat}")
            await self._client.get_permissions(chat, "me")
        except Exception:
            return
        
        delay = self.config["delay_seconds"]
        if delay > 0:
            await asyncio.sleep(delay)
        
        media_msg = await self._get_random_media("all")
        
        if media_msg:
            try:
                await self._client.send_file(
                    message.chat_id,
                    media_msg.media,
                    reply_to=message.id,
                    supports_streaming=True
                )
            except Exception as e:
                logger.debug(f"Watcher error: {e}")
