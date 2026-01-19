# Modification of the module is allowed only if the license is retained.
# MMP""MM""YMM 7MMF'   7MF' 7MM"""Mq.  7MM"""YMM
# P'   MM   7   MA     ,V    MM   MM.  MM   7
#      MM        VM:   ,V     MM   ,M9   MM   d
#      MM         MM.  M'     MMmmdM9    MMmmMM
#      MM         `MM A'      MM         MM   Y  ,
#      MM          :MM;       MM         MM    ,M
#    .JMML.          VF       .JMML.     .JMMmmmmMMM
#                 ,M
# This module is licensed and fully copyrighted by Type, copyright is allowed while maintaining the author's mention in the code.
# meta developer: @TypeModules
import logging
import random
import asyncio
import requests
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class TTrollMod(loader.Module):
    """
    Module for advanced trolling.
    Supports dictionaries, video inserts, and tagged modes.
    """
    
    strings = {
        "name": "T:Troll",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "delay",
                2.0,
                "Delay between messages (TagTroll) or before reply (GTroll)",
                validator=loader.validators.Float()
            ),
            loader.ConfigValue(
                "dict_url",
                "https://raw.githubusercontent.com/Foxinol/TypeModules/refs/heads/main/phrases.txt",
                "URL source for text phrases"
            ),
            loader.ConfigValue(
                "video_url",
                "https://pomf2.lain.la/f/fftxnkzc.mp4",
                "URL for the video attachment"
            ),
            loader.ConfigValue(
                "video_mode",
                "Random",
                "Video attachment mode",
                validator=loader.validators.Choice(["Off", "Random", "Always"])
            ),
        )
        self.gtroll_targets = set() # {(chat_id, user_id)}
        self.tagtroll_tasks = {} # {(chat_id, user_id): asyncio.Task}
        self.phrases = []

    async def client_ready(self, client, db):
        self.client = client

    async def _load_phrases(self):
        if self.phrases:
            return True
        try:
            url = self.config["dict_url"]
            r = await utils.run_sync(requests.get, url)
            r.raise_for_status()
            self.phrases = [line.strip() for line in r.text.splitlines() if line.strip()]
            return True
        except Exception as e:
            logger.error(f"Error loading phrases: {e}")
            return False

    async def _get_target(self, message):
        args = utils.get_args(message)
        if args and args[0].lower() == "stop":
            return "stop", "stop"
            
        reply = await message.get_reply_message()
        if reply:
            return reply.sender_id, "Target"
        
        if args:
            try:
                user = await self.client.get_entity(args[0])
                return user.id, "Target"
            except:
                pass
        return None, None

    async def _send_troll_message(self, chat_id, text, reply_to=None):
        video_mode = self.config["video_mode"]
        send_video = False

        if video_mode == "Always":
            send_video = True
        elif video_mode == "Random":
            send_video = random.random() < 0.3

        try:
            if send_video:
                await self.client.send_file(chat_id, self.config["video_url"], caption=text, reply_to=reply_to)
            else:
                await self.client.send_message(chat_id, text, reply_to=reply_to)
        except Exception as e:
            logger.error(f"Troll send error: {e}")
            try:
                await self.client.send_message(chat_id, text, reply_to=reply_to)
            except:
                pass

    async def _tagtroll_loop(self, chat_id, user_id):
        try:
            while True:
                if not self.phrases:
                    if not await self._load_phrases():
                        await asyncio.sleep(10)
                        continue
                
                text = random.choice(self.phrases)
                text = f"<a href='tg://user?id={user_id}'>{text}</a>"
                
                await self._send_troll_message(chat_id, text)
                
                delay = self.config["delay"]
                if delay < 0.1: delay = 0.1
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TagTroll loop error: {e}")

    @loader.command()
    async def gtroll(self, message):
        """<reply/user/stop> - Toggle reply trolling"""
        await message.delete()
        if not self.phrases:
            await self._load_phrases()

        target_id, _ = await self._get_target(message)
        
        if target_id == "stop":
            self.gtroll_targets.clear()
            return

        if not target_id:
            return

        key = (message.chat_id, target_id)
        if key in self.gtroll_targets:
            self.gtroll_targets.remove(key)
        else:
            self.gtroll_targets.add(key)

    @loader.command()
    async def tagtroll(self, message):
        """<reply/user/stop> - Toggle periodic tag trolling"""
        await message.delete()
        if not self.phrases:
            await self._load_phrases()

        target_id, _ = await self._get_target(message)

        if target_id == "stop":
            for task in self.tagtroll_tasks.values():
                task.cancel()
            self.tagtroll_tasks.clear()
            return

        if not target_id:
            return

        key = (message.chat_id, target_id)
        if key in self.tagtroll_tasks:
            self.tagtroll_tasks[key].cancel()
            del self.tagtroll_tasks[key]
        else:
            self.tagtroll_tasks[key] = asyncio.create_task(self._tagtroll_loop(message.chat_id, target_id))

    @loader.watcher(only_messages=True)
    async def watcher(self, message):
        if not self.gtroll_targets or message.out:
            return
            
        if not message.sender_id:
            return

        key = (message.chat_id, message.sender_id)
        if key not in self.gtroll_targets:
            return
        
        if not self.phrases:
             if not await self._load_phrases():
                 return

        if self.config["delay"] > 0:
            await asyncio.sleep(self.config["delay"])

        text = random.choice(self.phrases)
        await self._send_troll_message(message.chat_id, text, reply_to=message.id)

    async def on_unload(self):
        for task in self.tagtroll_tasks.values():
            task.cancel()
        self.tagtroll_tasks.clear()