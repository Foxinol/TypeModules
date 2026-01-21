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

import logging
import asyncio
import os
import random
import re
import time
import json
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession, SQLiteSession
from telethon.errors import FloodWaitError, UserNotParticipantError, ChannelPrivateError, SessionPasswordNeededError
from .. import loader, utils

try:
    import google.generativeai as genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

@loader.tds
class MultiFarmMod(loader.Module):
    """Multi-functional farm module"""

    strings = {
        "name": "MultiFarm",
        "no_arg_add": "<b>❌ Укажи номер телефона или String Session.</b>",
        "code_sent": "<b>📩 Код отправлен.</b>\nИспользуй <code>.mf_code &lt;код&gt;</code>",
        "2fa_needed": "<b>🔐 Нужен пароль 2FA.</b>\nИспользуй <code>.mf_2fa &lt;пароль&gt;</code>",
        "login_success": "<b>✅ Аккаунт {name} добавлен.</b>",
        "login_fail": "<b>❌ Ошибка входа:</b> <code>{e}</code>",
        "session_added": "<b>✅ Аккаунт {name} добавлен через String Session.</b>",
        "ref_start": "<b>🚀 Аккаунты стартуют бота по ссылке...</b>",
        "ref_done": "<b>✅ Готово.</b>",
        "ai_request": "<b>🧠 Отправляю запрос к Gemini...</b>",
        "ai_no_key": "<b>❌ Gemini API ключ не указан в конфиге.</b>",
        "ai_no_lib": "<b>❌ Библиотека <code>google-generativeai</code> не установлена.</b>\n<code>pip install google-generativeai</code>",
        "ai_done": "<b>🧠 Gemini применил новые настройки.</b>",
        "ai_fail": "<b>🧠 Ошибка при запросе к Gemini:</b>\n<code>{e}</code>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("status", False, "Статус модуля (вкл/выкл)"),
            # Farm settings
            loader.ConfigValue("farm_funstat", False, "Включить фарм в @funstatbot", validator=loader.validators.Boolean()),
            loader.ConfigValue("funstat_interval", "1h 1m", "Интервал для FunStat (e.g., '1h 30m 5s')"),
            loader.ConfigValue("funstat_spam_message", "Funstat Telelog ребят", "Сообщение для фарма в FunStat (должно содержать упоминание бота)"),
            loader.ConfigValue("farm_iris", False, "Включить фарм в @iris_cm_bot", validator=loader.validators.Boolean()),
            loader.ConfigValue("iris_interval", "4h 1m", "Интервал для Iris (e.g., '4h 5m')"),
            # Spam settings
            loader.ConfigValue("spam_mode", False, "Включить режим рассылки", validator=loader.validators.Boolean()),
            loader.ConfigValue("spam_interval", "1h", "Интервал для рассылки (e.g., '30m')"),
            loader.ConfigValue("target_chat", None, "ID, @username, ссылка на чат или ПАПКУ для рассылки"),
            loader.ConfigValue("message", "Hello!", "Сообщение для рассылки"),
            # AI settings
            loader.ConfigValue("gemini_api_key", None, "Gemini API Key for AI control", validator=loader.validators.Hidden()),
            loader.ConfigValue("gemini_prompt", "Analyze this MultiFarm module config. Suggest changes to optimize farming and spam. Respond ONLY with a JSON object of config keys and their new values.", "Prompt for Gemini AI"),
            loader.ConfigValue("admin_id", None, "User ID админа для уведомлений от ИИ", validator=loader.validators.Integer(minimum=1)),
            # Technical settings
            loader.ConfigValue("api_id", 0, "API ID (0 - по умолчанию)"),
            loader.ConfigValue("api_hash", "", "API HASH", validator=loader.validators.Hidden()),
        )
        self.active_clients = {}
        self.pending_login = {}
        self.task_loop_task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_loop_task = asyncio.create_task(self.task_scheduler())

    def _parse_time(self, time_str):
        if not time_str: return 0
        parts = re.findall(r'(\d+)\s*(s|m|h|d)', str(time_str))
        total_seconds = 0
        for value, unit in parts:
            value = int(value)
            if unit == 's': total_seconds += value
            elif unit == 'm': total_seconds += value * 60
            elif unit == 'h': total_seconds += value * 3600
            elif unit == 'd': total_seconds += value * 86400
        return total_seconds

    async def task_scheduler(self):
        await asyncio.sleep(10)
        while True:
            if not self.config["status"]:
                await asyncio.sleep(60)
                continue

            accounts = self.db.get("MultiFarm", "accounts", {})
            if not accounts:
                await asyncio.sleep(60)
                continue

            last_runs = self.db.get("MultiFarm", "last_runs", {})
            
            for phone, session_str in list(accounts.items()):
                now = int(time.time())
                if phone not in last_runs: last_runs[phone] = {}

                client = await self._get_client(phone, session_str)
                if not client: continue
                
                try:
                    # FunStat Farm
                    funstat_cd = self._parse_time(self.config['funstat_interval'])
                    if self.config["farm_funstat"] and now - last_runs[phone].get("funstat", 0) > funstat_cd:
                        await self._farm_funstat(client, phone)
                        last_runs[phone]["funstat"] = now
                        self.db.set("MultiFarm", "last_runs", last_runs)
                        await asyncio.sleep(random.randint(5, 10))

                    # Iris Farm
                    iris_cd = self._parse_time(self.config['iris_interval'])
                    if self.config["farm_iris"] and now - last_runs[phone].get("iris", 0) > iris_cd:
                        await self._farm_iris(client, phone)
                        last_runs[phone]["iris"] = now
                        self.db.set("MultiFarm", "last_runs", last_runs)
                        await asyncio.sleep(random.randint(5, 10))

                    # Spam Mode
                    spam_cd = self._parse_time(self.config['spam_interval'])
                    if self.config["spam_mode"] and now - last_runs[phone].get("spam", 0) > spam_cd:
                       await self._do_spam(client, phone)
                       last_runs[phone]["spam"] = now
                       self.db.set("MultiFarm", "last_runs", last_runs)
                       await asyncio.sleep(random.randint(5, 10))

                except FloodWaitError as e:
                    logger.warning(f"Flood wait for {phone}: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Scheduler error from {phone}: {e}", exc_info=True)
            
            await asyncio.sleep(30) # Main scheduler check interval

    async def _ensure_bot_started(self, client, phone, bot_name, start_link):
        initialized = self.db.get("MultiFarm", "initialized_bots", {})
        if phone not in initialized: initialized[phone] = []
        if bot_name in initialized[phone]: return True
        
        try:
            match = re.search(r"t\.me/(\w+)\?start=(\w+)", start_link)
            if not match: return False
            bot_username, start_payload = match.groups()
            await client.send_message(bot_username, f"/start {start_payload}")
            logger.info(f"Account {phone} started @{bot_username} for {bot_name}")
            initialized[phone].append(bot_name)
            self.db.set("MultiFarm", "initialized_bots", initialized)
            await asyncio.sleep(5)
            return True
        except Exception as e:
            logger.error(f"Failed to start {bot_name} for {phone}: {e}")
            return False

    async def _farm_funstat(self, client, phone):
        start_link = "https://funstat.info/?start=010125DE6DEA01000000"
        if not await self._ensure_bot_started(client, phone, "funstat", start_link): return
        
        target = self.config["target_chat"] if self.config["target_chat"] else "@flood"
        message = self.config["funstat_spam_message"]
        if "@funstatbot" not in message: message += " @funstatbot"
        
        await client.send_message(target, message)
        logger.info(f"Farming FunStat with {phone} in {target}")

    async def _farm_iris(self, client, phone):
        await client.send_message("@iris_cm_bot", "фарма")
        logger.info(f"Farming Iris with {phone}")

    async def _do_spam(self, client, phone, custom_message: str = None):
        target = self.config['target_chat']
        if not target: return

        message_to_send = custom_message or self.config["message"]
        
        targets = []
        if "t.me/addlist/" in target:
            folder_hash = target.split('/')[-1]
            target_folder = None
            
            try:
                await client(functions.messages.ImportChatlistInviteRequest(slug=folder_hash))
                logger.info(f"Join folder request sent for {phone}")
            except Exception as e:
                logger.warning(f"Could not join folder for {phone} (maybe already joined?): {e}")

            # Даем время на синхронизацию
            await asyncio.sleep(3)
            
            all_folders_obj = await client(functions.messages.GetDialogFiltersRequest())
            for folder in all_folders_obj: # ИСПРАВЛЕНА ЭТА СТРОКА
                if isinstance(folder, types.DialogFilter) and getattr(folder, 'slug', None) == folder_hash:
                    target_folder = folder
                    break

            if not target_folder:
                logger.error(f"FATAL: Could not find folder with slug {folder_hash} for account {phone}.")
                return

            try:
                dialogs = await client.get_dialogs(folder=target_folder.id)
                chats_in_folder = [d.entity for d in dialogs if d.is_channel or d.is_group]
                
                if not chats_in_folder:
                    logger.warning(f"Folder '{getattr(target_folder, 'title', 'N/A')}' for {phone} is empty.")
                else:
                    targets.extend(chats_in_folder)
            except Exception as e:
                logger.error(f"Could not get dialogs from folder for {phone}: {e}")
                return
        else:
            try:
                targets.append(await client.get_entity(target))
            except (ValueError, ChannelPrivateError):
                 logger.error(f"Invalid target chat for spam: {target}")
                 return
        
        for entity in targets:
            try:
                await client.send_message(entity, message_to_send)
                logger.info(f"Spam message sent by {phone} to {getattr(entity, 'title', entity.id)}")
                await asyncio.sleep(random.randint(3, 7))
            except UserNotParticipantError:
                 await client(functions.channels.JoinChannelRequest(entity))
                 await asyncio.sleep(3)
                 await client.send_message(entity, message_to_send)
                 logger.info(f"Joined and sent spam from {phone} to {getattr(entity, 'title', entity.id)}")
            except Exception as e:
                 logger.error(f"Spam error from {phone} to {getattr(entity, 'title', entity.id)}: {e}")

    @loader.command(ru_doc="<ссылка> - Запустить бота по реф. ссылке")
    async def mf_startref(self, message):
        link = utils.get_args_raw(message)
        if not link or "t.me/" not in link:
            return await utils.answer(message, "<b>❌ Укажи валидную ссылку.</b>")
            
        try:
            match = re.search(r"t\.me/(\w+)(?:\?start=(\w+))?", link)
            bot_username = match.group(1)
            start_payload = match.group(2)
            command = f"/start {start_payload}" if start_payload else "/start"
        except Exception:
            return await utils.answer(message, "<b>❌ Не удалось разобрать ссылку.</b>")
            
        await utils.answer(message, self.strings("ref_start"))
        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts: return await utils.answer(message, "🚫 <b>Нет добавленных аккаунтов.</b>")
            
        for phone, session_str in accounts.items():
            client = await self._get_client(phone, session_str)
            if not client: continue
            try:
                await client.send_message(bot_username, command)
                logger.info(f"Account {phone} sent '{command}' to @{bot_username}")
                await asyncio.sleep(random.randint(2, 5))
            except Exception as e:
                logger.error(f"Ref start error from {phone}: {e}")
                
        await utils.answer(message, self.strings("ref_done"))

    @loader.command(ru_doc="[промпт] - Оптимизировать настройки с помощью ИИ")
    async def mf_ai(self, message):
        if not genai: return await utils.answer(message, self.strings("ai_no_lib"))
        api_key = self.config["gemini_api_key"]
        if not api_key: return await utils.answer(message, self.strings("ai_no_key"))
        
        await utils.answer(message, self.strings("ai_request"))
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        current_config_str = json.dumps(self.config.to_dict(), indent=2)
        prompt = utils.get_args_raw(message) or self.config["gemini_prompt"]
        full_prompt = f"{prompt}\n\nHere is the current config:\n{current_config_str}"
        
        try:
            response = await model.generate_content_async(full_prompt)
            response_text = response.text.strip().replace("`", "").replace("json", "")
            changes = json.loads(response_text)
            
            log_changes = "<b>🧠 AI изменил настройки:</b>\n"
            for key, value in changes.items():
                if key in self.config:
                    self.config[key] = value
                    log_changes += f"<b>• {key}:</b> <code>{utils.escape_html(str(value))}</code>\n"
            
            await utils.answer(message, self.strings("ai_done"))
            if self.config["admin_id"]:
                await self.client.send_message(self.config["admin_id"], log_changes)

        except Exception as e:
            await utils.answer(message, self.strings("ai_fail").format(e=e))
    
    # --- Account Management ---
    
    @loader.command(ru_doc="<номер | string session> - Добавить аккаунт")
    async def mf_add(self, message):
        arg = utils.get_args_raw(message)
        if not arg: return await utils.answer(message, self.strings("no_arg_add"))
        api_id, api_hash = await self.get_api_credentials()
        sender_id = message.sender_id; client = None
        try:
            if arg.startswith("+"):
                if sender_id in self.pending_login: 
                    await self.pending_login[sender_id].get("client").disconnect()
                    del self.pending_login[sender_id]
                client = TelegramClient(StringSession(), api_id, api_hash); await client.connect()
                code_hash = await client.send_code_request(arg)
                self.pending_login[sender_id] = {"client": client, "phone": arg, "phone_code_hash": code_hash.phone_code_hash, "state": "code"}
                await utils.answer(message, self.strings("code_sent"))
            else:
                client = TelegramClient(StringSession(arg), api_id, api_hash); await client.connect()
                await self._finalize_login(client, message, self.strings("session_added"))
        except Exception as e: 
            await utils.answer(message, self.strings("login_fail").format(e=e))

    @loader.command(ru_doc="<code> - Ввести код")
    async def mf_code(self, message):
        sender_id = message.sender_id
        if sender_id not in self.pending_login or self.pending_login[sender_id].get("state") != "code": return
        pending = self.pending_login[sender_id]
        try:
            await pending["client"].sign_in(pending["phone"], utils.get_args_raw(message), phone_code_hash=pending["phone_code_hash"])
            await self._finalize_login(pending["client"], message, self.strings("login_success"))
            del self.pending_login[sender_id]
        except SessionPasswordNeededError:
            pending["state"] = "2fa"; await utils.answer(message, self.strings("2fa_needed"))
        except Exception as e:
            await utils.answer(message, self.strings("login_fail").format(e=e))
            if sender_id in self.pending_login: del self.pending_login[sender_id]

    @loader.command(ru_doc="<пароль> - Ввести пароль 2FA")
    async def mf_2fa(self, message):
        sender_id = message.sender_id
        if sender_id not in self.pending_login or self.pending_login[sender_id].get("state") != "2fa": return
        pending = self.pending_login[sender_id]
        try:
            await pending["client"].sign_in(password=utils.get_args_raw(message))
            await self._finalize_login(pending["client"], message, self.strings("login_success"))
            del self.pending_login[sender_id]
        except Exception as e:
            await utils.answer(message, self.strings("login_fail").format(e=e))
            if sender_id in self.pending_login: del self.pending_login[sender_id]

    async def _finalize_login(self, client, message, success_template):
        me = await client.get_me()
        
        try:
            await client(functions.channels.JoinChannelRequest("iris_cm"))
            logger.info(f"Account +{me.phone} successfully joined @iris_cm.")
        except Exception as e:
            logger.warning(f"Could not join @iris_cm for +{me.phone}: {e}")

        session_str = StringSession.save(client.session)
        phone = f"+{me.phone}"
        accounts = self.db.get("MultiFarm", "accounts", {})
        accounts[phone] = session_str
        self.db.set("MultiFarm", "accounts", accounts)
        
        if client is not self.client and client.is_connected():
            await client.disconnect()

        await utils.answer(message, success_template.format(name=utils.escape_html(me.first_name)))
        
        # Auto-update manage menu after adding
        await self.mf_managecmd(await self.client.send_message(message.peer_id, "Updating manage menu..."))

    @loader.command(ru_doc="<реплай на .session> - Добавить акк через файл")
    async def mf_session(self, message):
        reply = await message.get_reply_message()
        if not reply or not reply.file or not reply.file.name.endswith(".session"):
            return await utils.answer(message, "<b>❌ Ответь на файл <code>.session</code>.</b>")
            
        path = await message.client.download_file(reply.media)
        api_id, api_hash = await self.get_api_credentials()
        try:
            async with TelegramClient(SQLiteSession(path), api_id, api_hash) as client:
                me = await client.get_me()
                
                try:
                    await client(functions.channels.JoinChannelRequest("iris_cm"))
                    logger.info(f"Account +{me.phone} successfully joined @iris_cm via session file.")
                except Exception as e:
                    logger.warning(f"Could not join @iris_cm for +{me.phone} via session file: {e}")
                    
                phone = f"+{me.phone}"
                accounts = self.db.get("MultiFarm", "accounts", {})
                accounts[phone] = StringSession.save(client.session)
                self.db.set("MultiFarm", "accounts", accounts)
                await utils.answer(message, f"✅ <b>Аккаунт {utils.escape_html(me.first_name)} ({phone}) добавлен!</b>")
                await self.mf_managecmd(await self.client.send_message(message.peer_id, "Updating manage menu...")) # Auto-update manage menu
        except Exception as e: await utils.answer(message, f"❌ <b>Ошибка:</b> {e}")
        finally: 
            if os.path.exists(path): os.remove(path)

    @loader.command(ru_doc="- Управление аккаунтами")
    async def mf_managecmd(self, message):
        accounts = self.db.get("MultiFarm", "accounts", {})
        await self._show_accounts_page(message, 0)
    
    @loader.command(ru_doc="- Настройки модуля")
    async def mf_config(self, message):
        status = "🟢" if self.config["status"] else "🔴"
        funstat = "🟢" if self.config["farm_funstat"] else "🔴"
        iris = "🟢" if self.config["farm_iris"] else "🔴"
        spam = "🟢" if self.config["spam_mode"] else "🔴"
        
        txt = (f"⚙️ <b>Настройки MultiFarm</b>\n\n"
               f"{status} <b>Общий статус</b>\n\n"
               f"<b>🚜 Ферма:</b>\n"
               f"{funstat} FunStat | КД: <code>{self.config['funstat_interval']}</code>\n"
               f"{iris} Iris | КД: <code>{self.config['iris_interval']}</code>\n\n"
               f"<b>📨 Рассылка:</b>\n"
               f"{spam} Статус | КД: <code>{self.config['spam_interval']}</code>\n"
               f"🎯 <b>Цель:</b> <code>{self.config['target_chat']}</code>\n\n"
               f"<b>🧠 ИИ-контроль:</b>\n"
               f"🔑 <b>Gemini Key:</b> {'✅ Установлен' if self.config['gemini_api_key'] else '❌ Не установлен'}\n"
               f"👤 <b>Админ для логов:</b> <code>{self.config['admin_id']}</code>\n\n"
               f"<i>Используй <code>.config MultiFarm</code> для редактирования.</i>")
        await utils.answer(message, txt)

    @loader.command(ru_doc="- Принудительно запустить все активные задачи")
    async def mf_force(self, message):
        """Forces an immediate run of all enabled tasks, ignoring cooldowns"""
        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts:
            return await utils.answer(message, "🚫 <b>Нет добавленных аккаунтов для запуска.</b>")

        msg = await utils.answer(message, f"<b>🚀 Принудительно запускаю задачи на {len(accounts)} аккаунтах...</b>")

        success_count = 0
        for phone, session_str in accounts.items():
            client = await self._get_client(phone, session_str)
            if not client: continue
            try:
                if self.config["farm_iris"]:
                    await self._farm_iris(client, phone)
                    await asyncio.sleep(random.uniform(1, 2))
                if self.config["farm_funstat"]:
                    await self._farm_funstat(client, phone)
                    await asyncio.sleep(random.uniform(1, 2))
                if self.config["spam_mode"]:
                    await self._do_spam(client, phone)
                    await asyncio.sleep(random.uniform(1, 2))
                success_count += 1
                logger.info(f"[FORCED] Tasks executed for {phone}")
            except Exception as e:
                logger.error(f"[FORCED] Error on account {phone}: {e}")
            await asyncio.sleep(random.randint(2, 5))
        await msg.edit(f"<b>✅ Принудительный запуск завершен.</b>\n<b>Успешно обработано:</b> <code>{success_count}/{len(accounts)}</code>")

    @loader.command(ru_doc="<текст> - Рассылка своего текста в таргет")
    async def mf_targtx(self, message):
        """One-off spam to target with custom text"""
        text = utils.get_args_raw(message)
        if not text:
            return await utils.answer(message, "<b>❌ Укажи текст для рассылки.</b>")

        if not self.config["target_chat"]:
            return await utils.answer(message, "<b>❌ Цель для рассылки (target_chat) не указана в конфиге.</b>")

        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts:
            return await utils.answer(message, "🚫 <b>Нет добавленных аккаунтов для рассылки.</b>")

        msg = await utils.answer(message, f"<b>🔥 Начинаю рассылку на {len(accounts)} аккаунтах...</b>")
        
        success_count = 0
        for phone, session_str in accounts.items():
            client = await self._get_client(phone, session_str)
            if not client: continue
            try:
                await self._do_spam(client, phone, custom_message=text)
                success_count += 1
            except Exception as e:
                logger.error(f"[TGTX_SPAM] Error on account {phone}: {e}")
            await asyncio.sleep(random.randint(2, 5))
        
        await msg.edit(f"<b>✅ Рассылка завершена.</b>\n<b>Успешно отправлено с:</b> <code>{success_count}/{len(accounts)}</code> <b>аккаунтов.</b>")


    # --- Helpers & Inline ---
    async def get_api_credentials(self):
        return (self.config["api_id"], self.config["api_hash"]) if self.config["api_id"] else (self.client.api_id, self.client.api_hash)

    async def _get_client(self, phone, session_str):
        if phone in self.active_clients and self.active_clients[phone].is_connected(): return self.active_clients[phone]
        api_id, api_hash = await self.get_api_credentials()
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized(): raise ConnectionError("Revoked session")
            self.active_clients[phone] = client
            return client
        except Exception as e:
            logger.error(f"Failed to connect client {phone}: {e}. Removing.")
            accounts = self.db.get("MultiFarm", "accounts", {}); 
            if phone in accounts:
                del accounts[phone]
                self.db.set("MultiFarm", "accounts", accounts)
            return None

    async def _show_accounts_page(self, m, page):
        accounts = list(self.db.get("MultiFarm", "accounts", {}).keys())
        no_accounts = not accounts
        
        if no_accounts:
            text = "🚫 <b>Нет добавленных аккаунтов.</b>"
            keyboard = [[{"text": "➕ Добавить аккаунт", "callback": self._add_account_prompt}],[{"text": "❌ Закрыть", "action": "close"}]]
        else:
            chunk_size = 5
            total_pages = (len(accounts) + chunk_size - 1) // chunk_size or 1
            current_items = accounts[page * chunk_size : (page + 1) * chunk_size]
            keyboard = [[{"text": f"👤 {phone}", "callback": self._account_menu, "args": [phone]}] for phone in current_items]
            
            nav = []
            if page > 0: nav.append({"text": "⬅️", "callback": self._paginate, "args": [page - 1]})
            nav.append({"text": "➕", "callback": self._add_account_prompt})
            if page < total_pages - 1: nav.append({"text": "➡️", "callback": self._paginate, "args": [page + 1]})
            
            keyboard.append(nav)
            keyboard.append([{"text": "❌ Закрыть", "action": "close"}])
            text = f"👥 <b>Аккаунты (Стр. {page + 1}/{total_pages})</b>"

        if " form" in str(type(m)): # Check if it's an inline form
             await m.edit(text=text, reply_markup=keyboard)
        else:
             await self.inline.form(text=text, message=m, reply_markup=keyboard)


    async def _paginate(self, call, page): await self._show_accounts_page(call, int(page))
    async def _account_menu(self, call, phone): await call.edit(f"👤 <b>Управление:</b> <code>{phone}</code>", reply_markup=[[{"text": "🗑 Удалить", "callback": self._delete_acc_confirm, "args": [phone]}], [{"text": "🔙 Назад", "callback": self._paginate, "args": [0]}]])
    async def _add_account_prompt(self, call): await call.answer("Используй .mf_add <session / +7...>", show_alert=True)
    async def _delete_acc_confirm(self, call, phone): await call.edit(f"⚠️ <b>Удалить {phone}?</b>", reply_markup=[[{"text": "✅ Да", "callback": self._delete_acc_do, "args": [phone]}], [{"text": "❌ Нет", "callback": self._account_menu, "args": [phone]}]])
    async def _delete_acc_do(self, call, phone):
        accounts = self.db.get("MultiFarm", "accounts", {}); del accounts[phone]; self.db.set("MultiFarm", "accounts", accounts)
        if phone in self.active_clients: await self.active_clients.pop(phone).disconnect()
        await call.answer("Аккаунт удален.")
        
        # Auto-update manage menu after deleting
        await self._show_accounts_page(call, 0)