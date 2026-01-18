# Modification of the module is allowed only if the license is retained.
# MMP""MM""YMM 7MMF'   7MF' 7MM"""Mq.  7MM"""YMM
# P'   MM   7   MA     ,V     MM   MM.  MM   7
#     MM        VM:   ,V      MM   ,M9   MM   d
#     MM         MM.  M'      MMmmdM9    MMmmMM
#     MM         `MM A'       MM         MM   Y  ,
#     MM          :MM;        MM         MM     ,M
#   .JMML.         VF       .JMML.     .JMMmmmmMMM
#                  ,M
# This module is licensed and fully copyrighted by Type, copyright is allowed while maintaining the author's mention in the code.
# meta developer: @TypeModules

from .. import loader, utils
import time
import datetime
from telethon import functions, types

@loader.tds
class TAFKMod(loader.Module):
    """Модуль T:AFK
    По команде ставит в ник [AFK] и отвечает на сообщения.
    Ведет статистику пропущенных сообщений и времени в AFK.
    """
    strings = {"name": "T:AFK"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_message",
                "<b>Сейчас нахожусь в AFK!</b>\nПричина: {reason}\nПрошло • {afktime}",
                "Сообщение автоответа. Переменные: {afktime}, {reason}, {time}",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "timezone",
                3,
                "Часовой пояс (сдвиг от UTC, например 3 для МСК)",
                validator=loader.validators.Integer(),
            ),
        )
        self.ratelimit = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        # Инициализация глобальной статистики, если её нет
        if self.db.get("TAFK", "global_time") is None:
            self.db.set("TAFK", "global_time", 0)
        if self.db.get("TAFK", "global_msgs") is None:
            self.db.set("TAFK", "global_msgs", 0)
        if self.db.get("TAFK", "global_users") is None:
            self.db.set("TAFK", "global_users", [])

    def _format_time(self, seconds):
        """Форматирует секунды в ч м с"""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}ч {m}м {s}с"

    def _get_current_time(self):
        """Получает время с учетом конфига часового пояса"""
        offset = self.config["timezone"]
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=offset)
        return now.strftime("%H:%M:%S")

    @loader.command(ru_doc="[причина] - Войти/Выйти из режима AFK")
    async def afkcmd(self, message):
        """[reason] - Toggle AFK mode"""
        afk_state = self.db.get("TAFK", "is_afk", False)

        if afk_state:
            # === ВЫХОДИМ ИЗ AFK ===
            start_time = self.db.get("TAFK", "start_time", time.time())
            missed_msgs = self.db.get("TAFK", "missed_msgs", 0)
            missed_users = self.db.get("TAFK", "missed_users", [])
            
            duration = time.time() - start_time
            duration_str = self._format_time(duration)
            
            # Восстанавливаем имя
            original_first_name = self.db.get("TAFK", "original_first_name")
            if original_first_name:
                try:
                    await self.client(functions.account.UpdateProfileRequest(first_name=original_first_name))
                except Exception:
                    pass # Игнорируем ошибки смены имени
            
            # Обновляем глобальную статистику
            g_time = self.db.get("TAFK", "global_time", 0)
            g_msgs = self.db.get("TAFK", "global_msgs", 0)
            g_users = self.db.get("TAFK", "global_users", [])
            
            self.db.set("TAFK", "global_time", g_time + int(duration))
            self.db.set("TAFK", "global_msgs", g_msgs + missed_msgs)
            
            # Добавляем уникальных пользователей в глобальный список
            current_global_set = set(g_users)
            current_global_set.update(missed_users)
            self.db.set("TAFK", "global_users", list(current_global_set))

            # Сбрасываем статус
            self.db.set("TAFK", "is_afk", False)
            self.ratelimit = {} # Очищаем рейтлимит

            # Отчет
            text = (
                f"<b>Статус AFK отключен.</b>\n\n"
                f"За время AFK вам писало <b>{len(set(missed_users))}</b> пользователей.\n"
                f"Пропущено - <b>{missed_msgs}</b> сообщений.\n"
                f"Вы были в AFK: <b>{duration_str}</b>."
            )
            await utils.answer(message, text)

        else:
            # === ВХОДИМ В AFK ===
            args = utils.get_args_raw(message)
            reason = args if args else "Не указана"
            
            # Сохраняем текущее имя
            me = await self.client.get_me()
            self.db.set("TAFK", "original_first_name", me.first_name)
            
            # Меняем имя (добавляем [AFK])
            new_name = f"[AFK] {me.first_name}"
            # Telegram limit is 64 chars
            if len(new_name) > 64:
                new_name = new_name[:64]
            
            try:
                await self.client(functions.account.UpdateProfileRequest(first_name=new_name))
            except Exception:
                pass

            # Устанавливаем статус
            self.db.set("TAFK", "is_afk", True)
            self.db.set("TAFK", "start_time", time.time())
            self.db.set("TAFK", "reason", reason)
            self.db.set("TAFK", "missed_msgs", 0)
            self.db.set("TAFK", "missed_users", [])
            
            await utils.answer(message, f"<b>Режим AFK включен!</b>\nПричина: {reason}")

    @loader.command(ru_doc="- Показать глобальную статистику AFK")
    async def afkstatcmd(self, message):
        """Show global AFK statistics"""
        g_time = self.db.get("TAFK", "global_time", 0)
        g_msgs = self.db.get("TAFK", "global_msgs", 0)
        g_users = self.db.get("TAFK", "global_users", [])
        
        text = (
            "<b>📊 Global AFK Statistics</b>\n\n"
            f"🕰 Всего проведено в AFK: <b>{self._format_time(g_time)}</b>\n"
            f"📩 Всего пропущено сообщений: <b>{g_msgs}</b>\n"
            f"👥 Всего писало разных людей: <b>{len(g_users)}</b>"
        )
        await utils.answer(message, text)

    @loader.watcher(out=False, only_messages=True)
    async def watcher(self, message):
        if not self.db.get("TAFK", "is_afk", False):
            return

        # Игнорируем ботов и сервисные сообщения
        if message.sender_id is None or (hasattr(message.sender, 'bot') and message.sender.bot):
            return

        # Работаем только в ЛС
        if not message.is_private:
            return

        # Считаем статистику
        missed_msgs = self.db.get("TAFK", "missed_msgs", 0) + 1
        self.db.set("TAFK", "missed_msgs", missed_msgs)
        
        missed_users = self.db.get("TAFK", "missed_users", [])
        if message.sender_id not in missed_users:
            missed_users.append(message.sender_id)
            self.db.set("TAFK", "missed_users", missed_users)

        # Рейтлимит (чтобы не спамить в чат каждую секунду)
        # В ЛС раз в 30 сек
        now = time.time()
        limit_key = f"{message.chat_id}_{message.sender_id}"
        last_time = self.ratelimit.get(limit_key, 0)
        cooldown = 30
        
        if now - last_time < cooldown:
            return
        
        self.ratelimit[limit_key] = now

        # Формируем ответ
        start_time = self.db.get("TAFK", "start_time", time.time())
        reason = self.db.get("TAFK", "reason", "Не указана")
        afk_duration = self._format_time(time.time() - start_time)
        current_time = self._get_current_time()
        
        msg_text = self.config["default_message"].format(
            reason=reason,
            afktime=afk_duration,
            time=current_time
        )
        
        await utils.answer(message, msg_text)