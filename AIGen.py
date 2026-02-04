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
import asyncio

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
        "no_api_key": "🚫 <b>API-ключ для Gemini не установлен.</b>\nПолучи его <a href='https://makersuite.google.com/app/apikey'>здесь</a> и установи командой:\n<code>.config AIGen GEMINI_API_KEY=ваш_ключ</code>",
        "processing_gen": "🧠 <b>Думаю над твоей идеей... Ожидай ZIP</b>",
        "processing_fix": "🔧 <b>Изучаю код, готовлю правки...</b>",
        "processing_raw": "📡 <b>Получаю сырой ответ от ИИ...</b>",
        "api_error": "🚫 <b>Ошибка API Gemini.</b>\n<code>{}</code>",
        "api_error_permission": "🚫 <b>Ошибка API Gemini:</b>\n<code>Доступ запрещен. Вероятно, твой API-ключ недействителен или просрочен.</code>",
        "parse_error": "🤯 <b>ИИ вернул ответ в некорректном формате.</b>\n<i>Используй <code>.proj_raw</code>, чтобы увидеть его ответ.</i>",
        "no_reply": "☝️ <b>Ответь на сообщение с ZIP-архивом, который нужно исправить.</b>",
        "not_zip": "📎 <b>Это не ZIP-архив.</b>",
        "success": "✅ <b>Твой проект готов, Хозяин.</b>",
        "explanation_msg": "<b>Комментарии от ИИ:</b>\n{explanation}",
        "success_raw": "📥 <b>Сырой ответ от Gemini.</b>",
        "no_prompt": "❓ <b>А что генерировать-то? Опиши идею.</b>"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "GEMINI_API_KEY", None,
                doc=lambda: self.strings("config_gemini_api_key"),
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "GEMINI_MODEL", "gemini-1.5-pro-latest",
                doc=lambda: self.strings("config_gemini_model"),
            ),
        )

    # PROMPTS FOR CODE GENERATION
    def _get_gen_prompt(self, idea: str) -> str:
        return (
            "ТЫ — ЭЛИТНЫЙ PYTHON-РАЗРАБОТЧИК. ТВОЯ ЗАДАЧА — ПРЕДОСТАВИТЬ ТОЛЬКО КОД.\n"
            "ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ ИСКЛЮЧИТЕЛЬНО КОДОМ, БЕЗ ЕДИНОГО ЛИШНЕГО СЛОВА, ПРИВЕТСТВИЯ ИЛИ ПОЯСНЕНИЯ.\n\n"
            "ПРАВИЛА:\n"
            "1. ТЫ ОБЯЗАН предоставить код для ВСЕХ необходимых файлов (main.py, requirements.txt, и т.д.).\n"
            "2. КАЖДЫЙ ФАЙЛ ДОЛЖЕН НАЧИНАТЬСЯ СТРОГО с маркера: `--- имя_файла.расширение ---` НА ОТДЕЛЬНОЙ СТРОКЕ. Если есть папки, указывай путь: `--- папка/имя_файла.расширение ---`.\n"
            "3. После маркера вставляй ПОЛНЫЙ блок кода в формате ```python ... ```.\n"
            "4. НИКАКИХ СОКРАЩЕНИЙ И КОММЕНТАРИЕВ-ЗАГЛУШЕК.\n"
            "5. В файлах конфигурации используй заглушки типа 'ВАШ_ТОКЕН_ЗДЕСЬ'.\n"
            "6. Ты ОБЯЗАН создать файл `start.bat` для Windows. Он должен устанавливать зависимости из `requirements.txt` и запускать основной скрипт (например, `main.py`). Добавь `pause` в конце для отладки.\n\n"
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
            "4. Формат ответа СТРОГО такой же: маркер `--- папка/имя_файла.расширение ---` и ПОЛНЫЙ код этого файла в блоке ```python ... ```.\n\n"
            f"ИСХОДНЫЙ КОД:\n{code_to_fix}\n\n"
            f"ЗАДАЧА:\n{fix_request}"
        )

    # PROMPTS FOR EXPLANATION GENERATION
    def _get_gen_explanation_prompt(self, idea: str) -> str:
        return (
            "Ты — технический писатель и ассистент разработчика. Тебе дали задачу, по которой только что был сгенерирован код, включая `start.bat`.\n"
            "Твоя цель — написать краткое и понятное пояснение для пользователя.\n\n"
            "ПРАВИЛА:\n"
            "1. Напиши краткое описание того, что делает сгенерированный бот.\n"
            "2. Дай четкие инструкции по установке и запуску: сначала нужно вписать все токены и ID в конфиг-файлы, а потом просто запустить `start.bat`, который всё установит и запустит сам.\n"
            "3. Если есть важные моменты или советы по использованию, упомяни их.\n"
            "4. Говори кратко, по делу, используй Markdown для форматирования.\n\n"
            f"ИСХОДНАЯ ЗАДАЧА:\n{idea}"
        )

    def _get_fix_explanation_prompt(self, code_to_fix: str, fix_request: str) -> str:
        return (
            "Ты — опытный тимлид, который делает ревью кода. Твой коллега-ИИ только что внёс правки в проект по запросу. "
            "Твоя задача — изучить исходный код, запрос на исправление и написать краткий ченджлог (список изменений).\n\n"
            "ПРАВИЛА:\n"
            "1. Опиши, какие ключевые изменения были внесены в код.\n"
            "2. Объясни, почему эти изменения были сделаны, основываясь на запросе.\n"
            "3. Если были добавлены новые зависимости или изменены файлы конфигурации, обязательно укажи это.\n"
            "4. Говори кратко, по делу, как в отчёте. Используй Markdown.\n\n"
            f"ИСХОДНЫЙ КОД:\n{code_to_fix}\n\n"
            f"ЗАПРОС НА ИСПРАВЛЕНИЕ:\n{fix_request}"
        )

    async def _call_gemini(self, prompt_text: str):
        genai.configure(api_key=self.config["GEMINI_API_KEY"])
        model = genai.GenerativeModel(self.config["GEMINI_MODEL"])
        try:
            response = await model.generate_content_async(prompt_text, request_options={"timeout": 600})
            return response.text
        except core_exceptions.PermissionDenied:
            return "API_ERROR:PERMISSION_DENIED"
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"API_ERROR: {e}"

    async def _parse_and_zip(self, ai_response: str):
        strict_pattern = re.compile(r'--- ([\w\._/-]+) ---\s*```(?:[a-z]*\n)?(.*?)```', re.DOTALL)
        matches = strict_pattern.findall(ai_response)

        if not matches:
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, code in matches:
                zip_file.writestr(filename.strip(), code.strip().replace('\r\n', '\n'))
        
        zip_buffer.seek(0)
        return zip_buffer

    async def _handle_api_response(self, msg, ai_response):
        if ai_response.startswith("API_ERROR:"):
            error_msg = self.strings("api_error_permission") if "PERMISSION_DENIED" in ai_response else self.strings("api_error").format(ai_response.split(':', 1)[1].strip())
            await utils.answer(msg, error_msg)
            return None
            
        zip_buffer = await self._parse_and_zip(ai_response)
        if not zip_buffer:
            await utils.answer(msg, self.strings("parse_error"))
            return None
        
        return zip_buffer

    @loader.command(alias="pg")
    async def proj_gen(self, message):
        """<prompt> - Пишет бота по вашему ТЗ/Вашей идее"""
        if not self.config["GEMINI_API_KEY"]: return await utils.answer(message, self.strings("no_api_key"))
        idea = utils.get_args_raw(message)
        if not idea: return await utils.answer(message, self.strings("no_prompt"))

        msg = await utils.answer(message, self.strings("processing_gen"))

        code_prompt = self._get_gen_prompt(idea)
        explanation_prompt = self._get_gen_explanation_prompt(idea)

        code_task = self._call_gemini(code_prompt)
        explanation_task = self._call_gemini(explanation_prompt)
        
        ai_response_code, ai_explanation = await asyncio.gather(code_task, explanation_task)

        zip_buffer = await self._handle_api_response(msg, ai_response_code)
        if not zip_buffer: return

        zip_filename = f"project_{int(time.time())}.zip"
        
        file_msg = await self._client.send_file(
            message.peer_id,
            file=zip_buffer,
            caption=self.strings("success"),
            force_document=True,
            attributes=[DocumentAttributeFilename(zip_filename)]
        )
        
        explanation_text = self.strings("explanation_msg").format(explanation=ai_explanation)
        await self._client.send_message(message.peer_id, explanation_text, reply_to=file_msg.id)

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
            await utils.answer(msg, f"<b>Ошибка при чтении архива:</b>\n<code>{e}</code>")
            return
        if not code_to_fix:
            await utils.answer(msg, "<b>Не удалось прочитать файлы в архиве.</b>")
            return

        code_prompt = self._get_fix_prompt(code_to_fix, fix_request)
        explanation_prompt = self._get_fix_explanation_prompt(code_to_fix, fix_request)

        code_task = self._call_gemini(code_prompt)
        explanation_task = self._call_gemini(explanation_prompt)

        ai_response_code, ai_explanation = await asyncio.gather(code_task, explanation_task)
        
        zip_buffer = await self._handle_api_response(msg, ai_response_code)
        if not zip_buffer: return

        zip_filename = f"fixed_project_{int(time.time())}.zip"
        
        file_msg = await self._client.send_file(
            message.peer_id,
            file=zip_buffer,
            caption=self.strings("success"),
            force_document=True,
            attributes=[DocumentAttributeFilename(zip_filename)],
            reply_to=reply.id
        )

        explanation_text = self.strings("explanation_msg").format(explanation=ai_explanation)
        await self._client.send_message(message.peer_id, explanation_text, reply_to=file_msg.id)

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
                await utils.answer(msg, f"<b>Ошибка при чтении архива:</b>\n<code>{e}</code>")
                return
            if not code_to_fix:
                await utils.answer(msg, "<b>Не удалось прочитать файлы в архиве.</b>")
                return
            prompt = self._get_fix_prompt(code_to_fix, args)
        else:
            prompt = self._get_gen_prompt(args)
        
        ai_response = await self._call_gemini(prompt)
        
        if ai_response.startswith("API_ERROR:"):
            error_msg = self.strings("api_error_permission") if "PERMISSION_DENIED" in ai_response else self.strings("api_error").format(ai_response.split(':', 1)[1].strip())
            await utils.answer(msg, error_msg)
            return

        file = io.BytesIO(ai_response.encode('utf-8'))
        file.name = f"raw_response_{int(time.time())}.txt"
        
        await self._client.send_file(
            message.peer_id,
            file=file,
            caption=self.strings("success_raw")
        )
        if msg.out: await msg.delete()
