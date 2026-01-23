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
from telethon.errors import (
    FloodWaitError, UserNotParticipantError, ChannelPrivateError, 
    SessionPasswordNeededError, InviteHashExpiredError, InviteHashInvalidError,
    UserAlreadyParticipantError, MessageIdInvalidError
)
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
            loader.ConfigValue("target_chat", None, "ID, @username, ссылка на чат. Можно несколько через запятую."),
            loader.ConfigValue("message", "Hello!", "Сообщение для рассылки (поддерживает spintax {a|b|c})"),
            # AI settings
            loader.ConfigValue("gemini_api_key", None, "Gemini API Key for AI control", validator=loader.validators.Hidden()),
            loader.ConfigValue("gemini_model", "gemini-2.5-pro", "Модель Gemini для использования", validator=loader.validators.String()),
            loader.ConfigValue("gemini_prompt", "Analyze this MultiFarm config for optimal farming/spam. Key rules: 1. Respect bot cooldowns (Iris ~4h, Funstat ~1h) - don't set intervals lower. 2. IGNORE and DO NOT CHANGE text fields like 'message', 'funstat_spam_message', or any IDs. 3. Respond ONLY with a JSON object of keys and their new values.", "Prompt for Gemini AI"),
            loader.ConfigValue("admin_id", None, "User ID админа для уведомлений от ИИ", validator=loader.validators.Integer(minimum=1)),
            # Technical settings
            loader.ConfigValue("api_id", 0, "API ID (0 - по умолчанию)"),
            loader.ConfigValue("api_hash", "", "API HASH", validator=loader.validators.Hidden()),
            loader.ConfigValue("concurrency_limit", 10, "Макс. кол-во одновременных задач для аккаунтов", validator=loader.validators.Integer(minimum=1)),
        )
        self.active_clients = {}
        self.pending_login = {}
        self.task_loop_task = None
        self.semaphore = None
        self._target_failure_counts = {}
        self._target_failure_lock = asyncio.Lock()

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.semaphore = asyncio.Semaphore(self.config["concurrency_limit"])
        
        stats = self.db.get("MultiFarm", "stats", {})
        if "start_time" not in stats:
            stats["start_time"] = time.time()
            self.db.set("MultiFarm", "stats", stats)

        self.task_loop_task = asyncio.create_task(self.task_scheduler())

    async def on_unload(self):
        if self.task_loop_task:
            self.task_loop_task.cancel()
        for client in self.active_clients.values():
            if client.is_connected():
                await client.disconnect()
        self.active_clients.clear()

    def _inc_stat(self, key, value=1):
        stats = self.db.get("MultiFarm", "stats", {})
        stats[key] = stats.get(key, 0) + value
        self.db.set("MultiFarm", "stats", stats)

    async def semaphore_wrapper(self, func, *args, **kwargs):
        async with self.semaphore:
            return await func(*args, **kwargs)
    
    def _spin(self, text):
        pattern = re.compile(r'{([^{}]*)}')
        while True:
            match = pattern.search(text)
            if not match:
                break
            options = match.group(1).split('|')
            text = text.replace(match.group(0), random.choice(options), 1)
        return text

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

    async def _run_account_tasks(self, phone, session_str):
        try:
            now = int(time.time())
            last_runs = self.db.get("MultiFarm", "last_runs", {})
            if phone not in last_runs: last_runs[phone] = {}

            client = await self._get_client(phone, session_str)
            if not client: return

            funstat_cd = self._parse_time(self.config['funstat_interval'])
            if self.config["farm_funstat"] and now - last_runs[phone].get("funstat", 0) > funstat_cd:
                await self._farm_funstat(client, phone)
                last_runs[phone]["funstat"] = now
                self.db.set("MultiFarm", "last_runs", last_runs)
                await asyncio.sleep(random.uniform(1, 3))

            iris_cd = self._parse_time(self.config['iris_interval'])
            if self.config["farm_iris"] and now - last_runs[phone].get("iris", 0) > iris_cd:
                await self._farm_iris(client, phone)
                last_runs[phone]["iris"] = now
                self.db.set("MultiFarm", "last_runs", last_runs)
                await asyncio.sleep(random.uniform(1, 3))

            spam_cd = self._parse_time(self.config['spam_interval'])
            if self.config["spam_mode"] and now - last_runs[phone].get("spam", 0) > spam_cd:
                await self._do_spam(client, phone)
                last_runs[phone]["spam"] = now
                self.db.set("MultiFarm", "last_runs", last_runs)
                await asyncio.sleep(random.uniform(1, 3))

        except FloodWaitError as e:
            logger.warning(f"Flood wait for {phone}: {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Scheduler error for account {phone}: {e}", exc_info=False)

    async def task_scheduler(self):
        await asyncio.sleep(15)
        while True:
            if not self.config["status"]:
                await asyncio.sleep(60)
                continue

            accounts = self.db.get("MultiFarm", "accounts", {})
            if not accounts:
                await asyncio.sleep(60)
                continue

            # Reset failure counts for this run
            async with self._target_failure_lock:
                self._target_failure_counts.clear()

            tasks = [self.semaphore_wrapper(self._run_account_tasks, phone, session) for phone, session in accounts.items()]
            await asyncio.gather(*tasks)

            await self._prune_dead_targets()
            
            await asyncio.sleep(60)

    async def _prune_dead_targets(self):
        async with self._target_failure_lock:
            if not self._target_failure_counts:
                return

            num_accounts = len(self.db.get("MultiFarm", "accounts", {}))
            dead_targets = {target for target, count in self._target_failure_counts.items() if count >= num_accounts}

            if dead_targets:
                logger.info(f"Found {len(dead_targets)} globally dead targets. Pruning from config.")
                current_targets = [t.strip() for t in self.config["target_chat"].split(',')]
                new_targets = [t for t in current_targets if t not in dead_targets]
                self.config["target_chat"] = ", ".join(new_targets)

                if self.config["admin_id"]:
                    removed_str = "\n".join([f"• <code>{utils.escape_html(t)}</code>" for t in dead_targets])
                    try:
                        await self.client.send_message(
                            self.config["admin_id"],
                            f"<b>🗑️ MultiFarm | Мёртвые цели удалены</b>\n\n"
                            f"Следующие цели невалидны для всех аккаунтов и были удалены из конфига:\n{removed_str}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send admin notification about pruned targets: {e}")

    async def _farm_funstat(self, client, phone):
        targets = [t.strip() for t in self.config["target_chat"].split(',')] if self.config["target_chat"] else []
        target = targets[0] if targets else "@flood"
        
        message = self.config["funstat_spam_message"]
        if "@funstatbot" not in message: message += " @funstatbot"
        
        try:
            await self._ensure_bot_started(client, phone, "funstat", "https://funstat.info/?start=010125DE6DEA01000000")
            await client.send_message(target, message)
            self._inc_stat("funstat_farm_count")
            logger.info(f"Farming FunStat with {phone} in {target}")
        except Exception:
            logger.error(f"Failed to farm funstat in {target} for {phone}")

    async def _farm_iris(self, client, phone):
        await client.send_message("@iris_cm_bot", "фарма")
        self._inc_stat("iris_farm_count")
        logger.info(f"Farming Iris with {phone}")

    async def _send_spam_to_target(self, client, phone, entity, message_template):
        try:
            try:
                await client(functions.channels.JoinChannelRequest(entity))
                await asyncio.sleep(random.uniform(2, 4))
            except UserAlreadyParticipantError:
                pass 
            except Exception as e_join:
                logger.error(f"Failed to join {getattr(entity, 'title', entity.id)} for {phone}: {e_join}")
                self._inc_stat("spam_errors")
                return

            async with client.action(entity, 'typing'):
                await asyncio.sleep(random.uniform(1.5, 3.5))
                spun_message = self._spin(message_template)
                await client.send_message(entity, spun_message)
                self._inc_stat("spam_success")
                logger.info(f"Spam from {phone} to {getattr(entity, 'title', entity.id)}")
        except Exception as e_send:
            self._inc_stat("spam_errors")
            logger.error(f"Spam error from {phone} to {getattr(entity, 'title', entity.id)}: {e_send}")

    async def _do_spam(self, client, phone, custom_message: str = None):
        target_config = self.config['target_chat']
        if not target_config: return

        message_to_send = custom_message or self.config["message"]
        
        blacklist = self.db.get("MultiFarm", "per_account_blacklist", {}).get(phone, [])
        chat_list = [chat.strip() for chat in target_config.split(',') if chat.strip() and chat.strip() not in blacklist]
        
        targets = []
        for chat_identifier in chat_list:
            try:
                if 'joinchat/' in chat_identifier or '/+' in chat_identifier:
                    invite_hash = chat_identifier.split('/')[-1].replace('+', '')
                    updates = await client(functions.messages.ImportChatInviteRequest(invite_hash))
                    entity = next((chat for chat in updates.chats), None)
                    if entity: targets.append(entity)
                else:
                    targets.append(await client.get_entity(chat_identifier))
            except UserAlreadyParticipantError:
                try: targets.append(await client.get_entity(chat_identifier))
                except Exception: pass
            except Exception:
                logger.error(f"Could not process target '{chat_identifier}' for {phone}. Blacklisting.")
                blacklist.append(chat_identifier)
                async with self._target_failure_lock:
                    self._target_failure_counts[chat_identifier] = self._target_failure_counts.get(chat_identifier, 0) + 1

        # Update per-account blacklist in DB
        bl_db = self.db.get("MultiFarm", "per_account_blacklist", {})
        bl_db[phone] = blacklist
        self.db.set("MultiFarm", "per_account_blacklist", bl_db)

        if not targets:
            return

        tasks = [self._send_spam_to_target(client, phone, entity, message_to_send) for entity in targets]
        await asyncio.gather(*tasks)

    @loader.command(ru_doc="<инвайт-ссылка> <ссылка> - Пожаловаться (BETA)")
    async def mf_report(self, message):
        args = utils.get_args_raw(message).split()
        if len(args) != 2:
            return await utils.answer(message, "<b>❌ Неверный формат.</b>\nНужно: <code>.mf_report &lt;инвайт-ссылка&gt; &lt;ссылка на сообщение&gt;</code>")
        
        invite_link, msg_link = args
        
        match = re.search(r"t\.me/(c/)?([\w\d_]+)/(\d+)", msg_link)
        if not match:
            return await utils.answer(message, "<b>❌ Неверный формат ссылки на сообщение.</b>")

        message_id = int(match.group(3))
        
        if 'joinchat/' in invite_link or '/+' in invite_link:
            invite_hash = invite_link.split('/')[-1].replace('+', '')
        else:
            return await utils.answer(message, "<b>❌ Первая ссылка должна быть инвайт-ссылкой (<code>t.me/+...</code> или <code>t.me/joinchat/...</code>).</b>")

        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts:
            return await utils.answer(message, "🚫 <b>Нет аккаунтов для отправки жалоб.</b>")

        msg = await utils.answer(message, f"<b>🔥 Начинаю рейд на сообщение...</b>\n<b>Аккаунтов в работе:</b> <code>{len(accounts)}</code>")
        
        async def report_task(phone, session_str):
            client = await self._get_client(phone, session_str)
            if not client: return
            
            peer = None
            try:
                try:
                    updates = await client(functions.messages.ImportChatInviteRequest(invite_hash))
                    peer = next((chat for chat in updates.chats), None)
                    logger.info(f"Account {phone} joined via {invite_link}")
                except UserAlreadyParticipantError:
                    logger.info(f"Account {phone} already in chat, resolving peer...")
                    invite_info = await client(functions.messages.CheckChatInviteRequest(invite_hash))
                    if hasattr(invite_info, 'chat'):
                        peer = await client.get_entity(invite_info.chat)
                
                if not peer:
                    logger.error(f"Could not resolve peer for {phone} using invite link. Aborting.")
                    self._inc_stat("report_errors")
                    return
                
                await client(functions.messages.ReportRequest(
                    peer=peer,
                    id=[message_id],
                    reason=types.InputReportReasonSpam(message="")
                ))
                logger.info(f"Account {phone} reported message {msg_link}")
                self._inc_stat("report_success")
                await asyncio.sleep(random.uniform(1, 3))

            except (InviteHashExpiredError, InviteHashInvalidError):
                logger.error(f"Invite link is invalid or expired for {phone}.")
                self._inc_stat("report_errors")
            except MessageIdInvalidError:
                logger.error(f"Message ID invalid for {phone}. Maybe deleted or not visible.")
                self._inc_stat("report_errors")
            except Exception as e:
                logger.error(f"Report error from {phone}: {e}")
                self._inc_stat("report_errors")

        tasks = [self.semaphore_wrapper(report_task, phone, session_str) for phone, session_str in accounts.items()]
        await asyncio.gather(*tasks)

        stats = self.db.get("MultiFarm", "stats", {})
        success_count = stats.get("report_success", 0)

        await msg.edit(f"<b>✅ Рейд завершен.</b>\n<b>Всего успешных жалоб:</b> <code>{success_count}</code>")

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
            
        async def start_task(phone, session_str):
            client = await self._get_client(phone, session_str)
            if not client: return
            try:
                await client.send_message(bot_username, command)
                await asyncio.sleep(random.randint(2, 5))
            except Exception: pass
        
        tasks = [self.semaphore_wrapper(start_task, p, s) for p, s in accounts.items()]
        await asyncio.gather(*tasks)
                
        await utils.answer(message, self.strings("ref_done"))

    @loader.command(ru_doc="[промпт] - Оптимизировать настройки с помощью ИИ")
    async def mf_ai(self, message):
        if not genai: return await utils.answer(message, self.strings("ai_no_lib"))
        api_key = self.config["gemini_api_key"]
        if not api_key: return await utils.answer(message, self.strings("ai_no_key"))
        
        await utils.answer(message, self.strings("ai_request"))
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.config["gemini_model"])
            
            current_config_dict = {key: self.config[key] for key in self.config}
            prompt = utils.get_args_raw(message) or self.config["gemini_prompt"]
            full_prompt = f"{prompt}\n\nHere is the current config:\n{json.dumps(current_config_dict, indent=2)}"
            
            def generate():
                return model.generate_content(full_prompt)

            response = await asyncio.to_thread(generate)
            
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

    @loader.command(ru_doc="- Показать статистику работы модуля")
    async def mf_stats(self, message):
        stats = self.db.get("MultiFarm", "stats", {})
        accounts = self.db.get("MultiFarm", "accounts", {})
        target_chats_str = self.config.get("target_chat", "")
        target_chats = [chat for chat in target_chats_str.split(',') if chat.strip()] if target_chats_str else []

        start_time = stats.get("start_time", time.time())
        uptime_seconds = time.time() - start_time
        
        def format_uptime(seconds):
            days, rem = divmod(seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            uptime_str = ""
            if days: uptime_str += f"{int(days)}д "
            if hours: uptime_str += f"{int(hours)}ч "
            if minutes: uptime_str += f"{int(minutes)}м"
            return uptime_str if uptime_str else "меньше минуты"

        spam_s = stats.get("spam_success", 0)
        spam_e = stats.get("spam_errors", 0)
        spam_total = spam_s + spam_e
        spam_rate = (spam_s / spam_total * 100) if spam_total > 0 else 0

        report_s = stats.get("report_success", 0)
        report_e = stats.get("report_errors", 0)
        report_total = report_s + report_e
        report_rate = (report_s / report_total * 100) if report_total > 0 else 0

        text = (f"📊 <b>Статистика MultiFarm</b>\n\n"
                f"<b>🚀 Общее:</b>\n"
                f"  <b>• Время работы:</b> <code>{format_uptime(uptime_seconds)}</code>\n"
                f"  <b>• Активных аккаунтов:</b> <code>{len(accounts)}</code>\n"
                f"  <b>• Таргет-чатов:</b> <code>{len(target_chats)}</code>\n\n"
                f"<b>📨 Рассылка:</b>\n"
                f"  <b>• ✅ Успешно:</b> <code>{spam_s}</code>\n"
                f"  <b>• ❌ Ошибок:</b> <code>{spam_e}</code>\n"
                f"  <b>• 📈 Успешность:</b> <code>{spam_rate:.2f}%</code>\n\n"
                f"<b>🚜 Ферма:</b>\n"
                f"  <b>• 👁️ Iris:</b> <code>{stats.get('iris_farm_count', 0)}</code>\n"
                f"  <b>• 📊 FunStat:</b> <code>{stats.get('funstat_farm_count', 0)}</code>\n\n"
                f"<b>🛡️ Жалобы:</b>\n"
                f"  <b>• ✅ Успешно:</b> <code>{report_s}</code>\n"
                f"  <b>• ❌ Ошибок:</b> <code>{report_e}</code>\n"
                f"  <b>• 📈 Успешность:</b> <code>{report_rate:.2f}%</code>\n\n"
                f"<i>Используй <code>.mf_resetstats</code> для сброса.</i>")

        await utils.answer(message, text)

    @loader.command(ru_doc="- Сбросить статистику модуля")
    async def mf_resetstats(self, message):
        self.db.set("MultiFarm", "stats", {"start_time": time.time()})
        await utils.answer(message, "<b>✅ Статистика сброшена.</b>")

    @loader.command(ru_doc="- Справка по модулю")
    async def mf_doc(self, message):
        text = (f"📖 <b>Справка по модулю MultiFarm</b>\n\n"
                f"Этот модуль — ваш личный командный центр для управления армией Telegram-аккаунтов. Он предназначен для автоматизации фарма, рассылок и других действий.\n\n"
                f"<b>Основные команды:</b>\n"
                f"• <code>.mf_add &lt;+7...|сессия&gt;</code> - Добавить новый аккаунт.\n"
                f"• <code>.mf_manage</code> - Интерактивное меню управления аккаунтами.\n"
                f"• <code>.mf_config</code> - Показать текущие настройки модуля.\n"
                f"• <code>.mf_stats</code> - Показать детальную статистику работы.\n"
                f"• <code>.mf_resetstats</code> - Сбросить статистику.\n\n"
                f"<b>Команды действий:</b>\n"
                f"• <code>.mf_targtx &lt;текст&gt;</code> - Разовая рассылка вашего текста по целям.\n"
                f"• <code>.mf_report &lt;инвайт&gt; &lt;ссылка&gt;</code> - (BETA) Рейд жалобами на сообщение.\n"
                f"• <code>.mf_startref &lt;ссылка&gt;</code> - Запустить бота по реф. ссылке со всех аккаунтов.\n"
                f"• <code>.mf_force</code> - Принудительно запустить все активные задачи, игнорируя таймеры.\n\n"
                f"<b>Продвинутые функции:</b>\n"
                f"• <code>.mf_ai [промпт]</code> - Оптимизировать настройки с помощью ИИ.\n"
                f"• <b>Anti-Spam:</b> Модуль использует Spintax в сообщениях (<code>{'{привет|здарова}'}</code>), имитацию печати и динамические задержки для снижения риска бана.\n\n"
                f"<b>Канал разработчика:</b> @TypeModules")
        await utils.answer(message, text)
    
    # --- Account Management ---
    @loader.command(ru_doc="<номер | string session> - Добавить аккаунт")
    async def mf_add(self, message):
        arg = utils.get_args_raw(message)
        if not arg: return await utils.answer(message, self.strings("no_arg_add"))
        api_id, api_hash = await self.get_api_credentials()
        sender_id = message.sender_id
        try:
            if arg.startswith("+"):
                if sender_id in self.pending_login: 
                    await self.pending_login[sender_id].get("client").disconnect()
                client = TelegramClient(StringSession(), api_id, api_hash)
                await client.connect()
                code_hash = await client.send_code_request(arg)
                self.pending_login[sender_id] = {"client": client, "phone": arg, "phone_code_hash": code_hash.phone_code_hash, "state": "code"}
                await utils.answer(message, self.strings("code_sent"))
            else:
                client = TelegramClient(StringSession(arg), api_id, api_hash)
                await client.connect()
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
        except Exception: pass

        session_str = StringSession.save(client.session)
        phone = f"+{me.phone}"
        accounts = self.db.get("MultiFarm", "accounts", {})
        accounts[phone] = session_str
        self.db.set("MultiFarm", "accounts", accounts)
        
        if client.is_connected():
            await client.disconnect()

        await utils.answer(message, success_template.format(name=utils.escape_html(me.first_name)))
        await self.mf_manage(await self.client.send_message(message.peer_id, "Updating manage menu..."))

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
                phone = f"+{me.phone}"
                accounts = self.db.get("MultiFarm", "accounts", {})
                accounts[phone] = StringSession.save(client.session)
                self.db.set("MultiFarm", "accounts", accounts)
                await utils.answer(message, f"✅ <b>Аккаунт {utils.escape_html(me.first_name)} ({phone}) добавлен!</b>")
                await self.mf_manage(await self.client.send_message(message.peer_id, "Updating manage menu..."))
        except Exception as e: await utils.answer(message, f"❌ <b>Ошибка:</b> {e}")
        finally: 
            if os.path.exists(path): os.remove(path)

    @loader.command(ru_doc="- Управление аккаунтами")
    async def mf_manage(self, message):
        await self._show_accounts_page(message, 0)
    
    @loader.command(ru_doc="<текст> - Рассылка своего текста в таргет")
    async def mf_targtx(self, message):
        text = utils.get_args_raw(message)
        if not text: return await utils.answer(message, "<b>❌ Укажи текст.</b>")
        if not self.config["target_chat"]: return await utils.answer(message, "<b>❌ Цель не указана.</b>")
        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts: return await utils.answer(message, "🚫 <b>Нет аккаунтов.</b>")
        msg = await utils.answer(message, f"<b>🔥 Начинаю рассылку...</b>")
        
        tasks = []
        for phone, session in accounts.items():
            async def spam_task(p, s):
                client = await self._get_client(p, s)
                if client:
                    await self._do_spam(client, p, custom_message=text)
            
            tasks.append(self.semaphore_wrapper(spam_task, phone, session))

        await asyncio.gather(*tasks)
        await msg.edit(f"<b>✅ Рассылка завершена.</b>")

    @loader.command(ru_doc="- Принудительно запустить все активные задачи")
    async def mf_force(self, message):
        accounts = self.db.get("MultiFarm", "accounts", {})
        if not accounts: return await utils.answer(message, "🚫 <b>Нет аккаунтов.</b>")
        msg = await utils.answer(message, f"<b>🚀 Принудительно запускаю задачи...</b>")
        
        async def force_run(p, s):
            client = await self._get_client(p, s)
            if not client: return
            try:
                if self.config["farm_iris"]: await self._farm_iris(client, p)
                if self.config["farm_funstat"]: await self._farm_funstat(client, p)
                if self.config["spam_mode"]: await self._do_spam(client, p)
            except Exception as e:
                logger.error(f"Forced task error for {p}: {e}")
        
        tasks = [self.semaphore_wrapper(force_run, p, s) for p, s in accounts.items()]
        await asyncio.gather(*tasks)
        await msg.edit(f"<b>✅ Запуск завершен.</b>")

    # --- Helpers & Inline ---
    async def get_api_credentials(self):
        return (self.config["api_id"], self.config["api_hash"]) if self.config["api_id"] and self.config["api_hash"] else (self.client.api_id, self.client.api_hash)

    async def _get_client(self, phone, session_str):
        if phone in self.active_clients and self.active_clients.get(phone).is_connected():
            return self.active_clients[phone]
        
        api_id, api_hash = await self.get_api_credentials()
        client = TelegramClient(StringSession(session_str), api_id, api_hash, flood_sleep_threshold=120)
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
        
        if not accounts:
            text = "🚫 <b>Нет добавленных аккаунтов.</b>"
            kb = [[{"text": "➕ Добавить", "callback": self._add_account_prompt}],[{"text": "❌ Закрыть", "action": "close"}]]
        else:
            chunk = 5
            pages = (len(accounts) + chunk - 1) // chunk or 1
            items = accounts[page * chunk : (page + 1) * chunk]
            kb = [[{"text": f"👤 {p}", "callback": self._account_menu, "args": [p]}] for p in items]
            
            nav = []
            if page > 0: nav.append({"text": "⬅️", "callback": self._paginate, "args": [page - 1]})
            nav.append({"text": "➕", "callback": self._add_account_prompt})
            if page < pages - 1: nav.append({"text": "➡️", "callback": self._paginate, "args": [page + 1]})
            
            kb.append(nav)
            kb.append([{"text": "❌ Закрыть", "action": "close"}])
            text = f"👥 <b>Аккаунты (Стр. {page + 1}/{pages})</b>"

        if hasattr(m, 'form'):
             await m.edit(text=text, reply_markup=kb)
        else:
             await self.inline.form(text=text, message=m, reply_markup=kb)

    async def _paginate(self, call, page): await self._show_accounts_page(call, int(page))
    async def _account_menu(self, call, phone): await call.edit(f"👤 <b>Управление:</b> <code>{phone}</code>", reply_markup=[[{"text": "🗑 Удалить", "callback": self._delete_acc_confirm, "args": [phone]}], [{"text": "🔙 Назад", "callback": self._paginate, "args": [0]}]])
    async def _add_account_prompt(self, call): await call.answer("Используй .mf_add <session / +7...>", show_alert=True)
    async def _delete_acc_confirm(self, call, phone): await call.edit(f"⚠️ <b>Удалить {phone}?</b>", reply_markup=[[{"text": "✅ Да", "callback": self._delete_acc_do, "args": [phone]}], [{"text": "❌ Нет", "callback": self._account_menu, "args": [phone]}]])
    async def _delete_acc_do(self, call, phone):
        accounts = self.db.get("MultiFarm", "accounts", {}); del accounts[phone]; self.db.set("MultiFarm", "accounts", accounts)
        if phone in self.active_clients and self.active_clients.get(phone).is_connected():
            await self.active_clients.pop(phone).disconnect()
        await call.answer("Аккаунт удален.")
        await self._show_accounts_page(call, 0)
