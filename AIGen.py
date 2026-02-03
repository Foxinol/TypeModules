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

import io
import os
import re
import time
import zipfile
import logging

import google.generativeai as genai
from google.api_core import exceptions as core_exceptions
from telethon.tl.types import DocumentAttributeFilename

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AIGenMod(loader.Module):
    """Сделает (или пофиксит) из вашего ТЗ полного Telegram бота и отдаст ZIP"""

    strings = {
        "name": "AIGen",
        "config_gemini_api_key": "Твой Gemini API Key",
        "config_gemini_model": "Модель Gemini для генерации (по умолчанию gemini-1.0-pro)",
        "no_api_key": "<emoji document_id=5325731399324310531>🚫</emoji> <b>API-ключ для Gemini не установлен.</b>\nПолучи его <a href='https://makersuite.google.com/app/apikey'>здесь</a> и установи командой:\n<code>.config AIGen GEMINI_API_KEY=ваш_ключ</code>",
        "processing_gen": "<emoji document_id=5451433383841105436>🧠</emoji> <b>Думаю над твоей идеей... Ожидай ZIP</b>",
        "processing_fix": "<emoji document_id=5451393667104113334>🔧</emoji> <b>Изучаю код, готовлю правки...</b>",
        "processing_raw": "<emoji document_id=5415922312630116743>📡</emoji> <b>Получаю сырой ответ от ИИ...</b>",
        "api_error": "<emoji document_id=5325731399324310531>🚫</emoji> <b>Ошибка API Gemini.</b>\n<code>{}</code>",
        "api_error_permission": "<emoji document_id=5325731399324310531>🚫</emoji> <b>Ошибка API Gemini:</b>\n<code>Доступ запрещен. Вероятно, твой API-ключ недействителен или просрочен.</code>",
        "parse_error": "<emoji document_id=5212356549318025123>🤯</emoji> <b>ИИ вернул ответ в некорректном формате.</b>\n<i>Используй <code>.proj_raw</code>, чтобы увидеть его ответ.</i>",
        "no_reply": "<emoji document_id=5312526093374390483>☝️</emoji> <b>Ответь на сообщение с ZIP-архивом, который нужно исправить.</b>",
        "not_zip": "<emoji document_id=5813136294747047805>📎</emoji> <b>Это не ZIP-архив.</b>",
        "success": "<emoji document_id=5312526093374390483>✅</emoji> <b>Твой проект готов, Хозяин.</b>",
        "success_raw": "<emoji document_id=5415922312630116743>📥</emoji> <b>Сырой ответ от Gemini.</b>",
        "no_prompt": "<emoji document_id=5312526093374390483>❓</emoji> <b>А что генерировать-то? Опиши идею.</b>"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "GEMINI_API_KEY", None,
                doc=lambda: self.strings("config_gemini_api_key"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "GEMINI_MODEL", "gemini-2.5-pro",
                doc=lambda: self.strings("config_gemini_model"),
            ),
        )

    def _get_gen_prompt(self, idea: str) -> str:
        return (
            "ТЫ — ЭЛИТНЫЙ PYTHON-РАЗРАБОТЧИК. ТВОЯ ЗАДАЧА — ПРЕДОСТАВИТЬ ТОЛЬКО КОД.\n"
            "ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ИСКЛЮЧИТЕЛЬНО КОДОМ, БЕЗ ЕДИНОГО ЛИШНЕГО СЛОВА, ПРИВЕТСТВИЯ ИЛИ ПОЯСНЕНИЯ.\n\n"
            "ПРАВИЛА:\n"
            "1. ТЫ ОБЯЗАН предоставить код для ВСЕХ необходимых файлов (main.py, requirements.txt, и т.д.).\n"
            "2. КАЖДЫЙ ФАЙЛ ДОЛЖЕН НАЧИНАТЬСЯ СТРОГО с маркера: `--- имя_файла.расширение ---` НА ОТДЕЛЬНОЙ СТРОКЕ.\n"
            "3. После маркера вставляй ПОЛНЫЙ блок кода в формате ```python ... ```.\n"
            "4. НИКАКИХ СОКРАЩЕНИЙ И КОММЕНТАРИЕВ-ЗАГЛУШЕК.\n"
            "5. В файлах конфигурации используй заглушки типа 'ВАШ_ТОКЕН_ЗДЕСЬ'.\n\n"
            f"ЗАДАЧА:\n{idea}"
        )

    def _get_fix_prompt(self, code_to_fix: str, fix_request: str) -> str:
        return (
            "ТЫ — ЭЛИТНЫЙ PYTHON-РАЗРАБОТЧИК. Тебе предоставлен код и задача по его исправлению.\n"
            "ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ИСКЛЮЧИТЕЛЬНО ИСПРАВЛЕННЫМ КОДОМ, БЕЗ ПОЯСНЕНИЙ.\n\n"
            "ПРАВИЛА:\n"
            "1. Внимательно изучи предоставленный код.\n"
            "2. Ты ОБЯЗАН предоставить ПОЛНЫЙ и ИСПРАВЛЕННЫЙ код для КАЖДОГО файла проекта, даже если изменения коснулись только одного.\n"
            "3. ЗАПРЕЩЕНО использовать сокращения, комментарии типа «# тут код без изменений». Отдай весь, сука, код целиком.\n"
            "4. Формат ответа СТРОГО такой же: маркер `--- имя_файла.расширение ---` и ПОЛНЫЙ код этого файла в блоке ```python ... ```.\n\n"
            f"ИСХОДНЫЙ КОД:\n{code_to_fix}\n\n"
            f"ЗАДАЧА:\n{fix_request}"
        )

    async def _call_gemini(self, prompt_text: str):
        genai.configure(api_key=self.config["GEMINI_API_KEY"])
        model = genai.GenerativeModel(self.config["GEMINI_MODEL"])
        try:
            response = await model.generate_content_async(prompt_text)
            return response.text
        except core_exceptions.PermissionDenied:
            return "API_ERROR:PERMISSION_DENIED"
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"API_ERROR: {e}"

    async def _parse_and_zip(self, ai_response: str):
        strict_pattern = re.compile(r'--- ([\w\._-]+) ---\s*```(?:\w*\n)?(.*?)```', re.DOTALL)
        matches = strict_pattern.findall(ai_response)

        if not matches:
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, code in matches:
                zip_file.writestr(filename.strip(), code.strip())
        
        zip_buffer.seek(0)
        return zip_buffer

    async def _handle_api_response(self, msg, ai_response):
        if ai_response.startswith("API_ERROR:"):
            error_msg = self.strings("api_error_permission") if "PERMISSION_DENIED" in ai_response else self.strings("api_error").format(ai_response.split(':', 1)[1].strip())
            await msg.edit(error_msg)
            return None
            
        zip_buffer = await self._parse_and_zip(ai_response)
        if not zip_buffer:
            await msg.edit(self.strings("parse_error"))
            return None
        
        return zip_buffer

    @loader.command(alias="pg")
    async def proj_gen(self, message):
        """<prompt> - Пишет бота по вашему ТЗ/Вашей идее"""
        if not self.config["GEMINI_API_KEY"]: return await utils.answer(message, self.strings("no_api_key"))
        idea = utils.get_args_raw(message)
        if not idea: return await utils.answer(message, self.strings("no_prompt"))

        msg = await utils.answer(message, self.strings("processing_gen"))
        prompt = self._get_gen_prompt(idea)
        ai_response = await self._call_gemini(prompt)

        zip_buffer = await self._handle_api_response(msg, ai_response)
        if not zip_buffer: return

        zip_filename = f"project_{int(time.time())}.zip"
        await self._client.send_file(
            message.peer_id, file=zip_buffer, caption=self.strings("success"),
            force_document=True, attributes=[DocumentAttributeFilename(zip_filename)]
        )
        if msg.out: await msg.delete()

    @loader.command(alias="pf")
    async def proj_fix(self, message):
        """<prompt> - Фикс/Модификация кода (реплай на ZIP)"""
        if not self.config["GEMINI_API_KEY"]: return await utils.answer(message, self.strings("no_api_key"))
        reply = await message.get_reply_message()
        fix_request = utils.get_args_raw(message)

        if not (reply and reply.file and reply.file.name.lower().endswith(".zip")):
            return await utils.answer(message, self.strings("no_reply"))
        if not fix_request: return await utils.answer(message, self.strings("no_prompt"))

        msg = await utils.answer(message, self.strings("processing_fix"))
        
        code_to_fix = ""
        try:
            with io.BytesIO() as file_stream:
                await self._client.download_file(reply.document, file_stream)
                file_stream.seek(0)
                with zipfile.ZipFile(file_stream, 'r') as zf:
                    for filename in zf.namelist():
                        if filename.endswith('/') or os.path.basename(filename).startswith('.'): continue
                        try:
                            content = zf.read(filename).decode('utf-8')
                            code_to_fix += f"--- {filename} ---\n```\n{content}\n```\n\n"
                        except (UnicodeDecodeError, KeyError): continue
        except Exception as e:
            await msg.edit(f"<b>Ошибка при чтении архива:</b>\n<code>{e}</code>")
            return
        if not code_to_fix:
            await msg.edit("<b>Не удалось прочитать файлы в архиве.</b>")
            return

        prompt = self._get_fix_prompt(code_to_fix, fix_request)
        ai_response = await self._call_gemini(prompt)
        
        zip_buffer = await self._handle_api_response(msg, ai_response)
        if not zip_buffer: return

        zip_filename = f"fixed_project_{int(time.time())}.zip"
        await self._client.send_file(
            message.peer_id, file=zip_buffer, caption=self.strings("success"),
            force_document=True, attributes=[DocumentAttributeFilename(zip_filename)], reply_to=reply.id
        )
        if msg.out: await msg.delete()

    @loader.command(alias="pr")
    async def proj_raw(self, message):
        """<prompt> - Отдаёт RAW (или сырой ответ) от Gemini (debugging)"""
        if not self.config["GEMINI_API_KEY"]: return await utils.answer(message, self.strings("no_api_key"))
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args: return await utils.answer(message, self.strings("no_prompt"))
            
        msg = await utils.answer(message, self.strings("processing_raw"))

        prompt = ""
        if reply and reply.file and reply.file.name.lower().endswith(".zip"):
            code_to_fix = ""
            try:
                with io.BytesIO() as file_stream:
                    await self._client.download_file(reply.document, file_stream)
                    file_stream.seek(0)
                    with zipfile.ZipFile(file_stream, 'r') as zf:
                        for filename in zf.namelist():
                            if filename.endswith('/') or os.path.basename(filename).startswith('.'): continue
                            try:
                                content = zf.read(filename).decode('utf-8')
                                code_to_fix += f"--- {filename} ---\n```\n{content}\n```\n\n"
                            except (UnicodeDecodeError, KeyError): continue
            except Exception as e:
                await msg.edit(f"<b>Ошибка при чтении архива:</b>\n<code>{e}</code>")
                return
            if not code_to_fix:
                await msg.edit("<b>Не удалось прочитать файлы в архиве.</b>")
                return
            prompt = self._get_fix_prompt(code_to_fix, args)
        else:
            prompt = self._get_gen_prompt(args)
        
        ai_response = await self._call_gemini(prompt)
        
        if ai_response.startswith("API_ERROR:"):
            error_msg = self.strings("api_error_permission") if "PERMISSION_DENIED" in ai_response else self.strings("api_error").format(ai_response.split(':', 1)[1].strip())
            await msg.edit(error_msg)
            return

        file = io.BytesIO(ai_response.encode('utf-8'))
        file.name = f"raw_response_{int(time.time())}.txt"
        await self._client.send_file(message.peer_id, file=file, caption=self.strings("success_raw"))
        if msg.out: await msg.delete()
