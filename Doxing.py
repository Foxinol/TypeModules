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

import asyncio
import re
from telethon.tl.types import Message

from .. import loader, utils

@loader.tds
class DoxingMod(loader.Module):
    """Модуль для доксинга через бота."""

    strings = {
        "name": "Doxing",
        "doxing": "<b><emoji document_id=5332688668102525212>⌛️</emoji> Загружаем данные, подождите...</b>",
        "no_args": "<b><emoji document_id=5465415354968735237>🚫</emoji> Не указана цель.</b>\n<i>Используй: .doxing <@username/ID/номер> или ответь на сообщение.</i>",
        "not_found": "<b><emoji document_id=5332279078546343321>🤷‍♂️</emoji> Информация не найдена.</b>",
        "limit_error": "<b>⚠️ Ваш лимит запросов временно исчерпан.</b>\n<i>Попробуйте позже.</i>",
        "bot_unreachable": "<b><emoji document_id=5465415354968735237>🚫</emoji> Бот для доксинга не отвечает.</b>",
        "phone_found": "<b><emoji document_id=5429571366384842791>🔎</emoji> Найден номер, запрашиваем доп. информацию...</b>"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "doxing_bot",
                "auto",
                lambda: "Юзернейм бота для доксинга. 'auto' - для использования реферального бота по умолчанию.",
                validator=loader.validators.String(),
            )
        )

    async def client_ready(self, client, db):
        self.client = client
        if self.config["doxing_bot"] == "auto":
            self.bot = "StarSHRobot"
            self.ref_link = "https://t.me/StarSHRobot?start=_ref_J55KZ22H9_X3QAyKjIF"
        else:
            self.bot = self.config["doxing_bot"].replace("@", "")
            self.ref_link = f"https.t.me/{self.bot}"

    async def doxingcmd(self, message: Message):
        """<@username/ID/номер> или реплай - запустить поиск инфы."""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        target = None
        if args:
            target = args
        elif reply:
            target = str(reply.sender_id)
        
        if not target:
            await utils.answer(message, self.strings["no_args"])
            return

        await utils.answer(message, self.strings["doxing"])
        
        try:
            async with self.client.conversation(self.bot, timeout=60) as conv:
                await conv.send_message(target)
                first_response = await conv.get_response()

                if "Выберите направление для поиска" in first_response.text and first_response.buttons:
                    await first_response.click(text="Telegram")
                    first_response = await conv.get_response()

                if "лимит запросов временно исчерпан" in first_response.text:
                    await utils.answer(message, self.strings["limit_error"])
                    return
                
                output = "<b><emoji document_id=5408928177307287446>👋</emoji> Братух, ты допизделся) Ща будет..</b>\n"
                found_anything = False
                
                text = first_response.text
                
                if "Не удалось найти информацию" not in text and "информации не найдено" not in text:
                    id_match = re.search(r"ID:<\/b> <code>(\d+)<\/code>", text)
                    if id_match:
                        user_id = id_match.group(1)
                        output += f"\n<emoji document_id=5409215691008017959>✈️</emoji> <b>Информация об аккаунте</b>\n"
                        output += f'<emoji document_id=5332279078546343321>🤷‍♂️</emoji> <b>Айди:</b> <a href="tg://user?id={user_id}">{user_id}</a>\n'
                        found_anything = True

                    phones_match = re.search(r"Телефон:<\/b> <code>(.*?)<\/code>", text)
                    if phones_match:
                        output += f"\n<emoji document_id=5294096239464295059>🔵</emoji> <b>Телефоны:</b> <code>{phones_match.group(1)}</code>\n"
                        found_anything = True
                    
                    history_match = re.search(r"История изменения имени:<\/b>\n([\s\S]+?)(?=\n\n|<)", text)
                    if history_match:
                        output += f"\n<emoji document_id=5251253128937897645>✋</emoji> <b>История имён:</b>\n<code>{history_match.group(1).strip()}</code>\n"
                        found_anything = True
                    
                    contacts_match = re.search(r"Контактные связи:<\/b> <blockquote expandable>(.*?)<\/blockquote>", text)
                    if contacts_match:
                        output += f"\n<emoji document_id=5258513401784573443>👥</emoji> <b>Контактные связи:</b>\n<code>{contacts_match.group(1).strip()}</code>\n"
                        found_anything = True

                    groups_match = re.search(r"Группы:<\/b> <blockquote expandable>([\s\S]+?)<\/blockquote>", text)
                    if groups_match:
                        output += f"\n👥 <b>Общие группы:</b>\n{groups_match.group(1).strip()}\n"
                        found_anything = True
                    
                    gifts_match = re.search(r"Подарочные связи:<\/b> <blockquote expandable>(.*?)<\/blockquote>", text)
                    if gifts_match:
                        output += f"\n🎁 <b>Подарочные связи:</b>\n<code>{gifts_match.group(1).strip()}</code>\n"
                        found_anything = True
                
                phone_match = re.search(r'Телефон:.*?<code>(\+?\d{9,})', first_response.text)
                if phone_match and phone_match.group(1).split(',')[0].strip() != re.sub(r'\D', '', target):
                    await utils.answer(message, self.strings["phone_found"])
                    phone_number = phone_match.group(1).split(',')[0].strip()
                    await asyncio.sleep(1)
                    await conv.send_message(phone_number)
                    second_response = await conv.get_response()
                    second_text = second_response.text

                    if "Не удалось найти информацию" not in second_text and "информации не найдено" not in second_text:
                        num_info_match = re.search(r"Телефон:.*?<code>(.*?)</code>\n.*?Оператор:<\/b> (.*?)\n.*?Страна:<\/b> (.*?)\n", second_text)
                        if num_info_match:
                            output += f"\n<emoji document_id=5294096239464295059>🔵</emoji> <b>Информация о номере</b>\n"
                            output += f"📞 <b>Номер:</b> <code>{num_info_match.group(1).strip()}</code>\n"
                            output += f"<emoji document_id=5258503720928288433>ℹ️</emoji> <b>Оператор:</b> <code>{num_info_match.group(2).strip()}</code>\n"
                            output += f"<emoji document_id=5397730656400714154>🏳️</emoji> <b>Страна:</b> <code>{num_info_match.group(3).strip()}</code>\n"
                            found_anything = True
                        
                        phone_books_match = re.search(r"Телефонные книги:<\/b> (.*?)\n", second_text)
                        if phone_books_match:
                            output += f"\n<emoji document_id=5258513401784573443>👥</emoji> <b>Как записан:</b> <code>{phone_books_match.group(1).strip()}</code>\n"
                            found_anything = True

                        socials = re.findall(r"((?:Вконтакте|Telegram):<\/b> <a href=.*?>.*?<\/a>.*?)\n", second_text)
                        if socials:
                            output += "\n"
                            for social in socials:
                                output += f"🧑‍💻 {social}\n"
                            found_anything = True
                
                if not found_anything:
                    await utils.answer(message, self.strings["not_found"])
                    return

                await utils.answer(message, output)

        except asyncio.TimeoutError:
            await utils.answer(message, self.strings["bot_unreachable"])
        except Exception as e:
            await utils.answer(message, f"<b>Произошла неведомая хуйня:</b>\n<code>{e}</code>")

    async def doxstatuscmd(self, message: Message):
        """Показывает, какой бот используется для доксинга."""
        await utils.answer(message, f"<b>🤖 Текущий бот:</b> <a href='{self.ref_link}'>{self.bot}</a>")
