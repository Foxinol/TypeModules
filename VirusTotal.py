# meta developer: @TypeModules

from .. import loader, utils
import aiohttp
import asyncio
import hashlib
import logging

logger = logging.getLogger(__name__)


@loader.tds
class VirusTotalMod(loader.Module):
    """Module for scanning files on VirusTotal with beautiful formatting"""

    strings = {
        "name": "VirusTotal",
        "no_api_key": "🔑 <b>API key not set!</b>\n\nGet your API key at <a href='https://www.virustotal.com/gui/my-apikey'>VirusTotal</a> and set it via <code>.config VirusTotal</code>",
        "no_file": "📎 <b>Reply to a file to scan it!</b>",
        "downloading": "📥 <b>Downloading file...</b>",
        "checking_hash": "🔍 <b>Checking if file was already scanned...</b>",
        "uploading": "📤 <b>Uploading file to VirusTotal...</b>",
        "analyzing": "🔬 <b>Analyzing file...</b>\n<i>This may take a few minutes</i>",
        "error": "❌ <b>Error:</b> <code>{}</code>",
        "file_too_large": "📦 <b>File is too large!</b>\nMaximum size: 32 MB",
        "result_title": "🛡 <b>VirusTotal Scan Results</b>",
        "file_name": "📄 <b>File:</b> <code>{}</code>",
        "file_size": "📊 <b>Size:</b> <code>{}</code>",
        "detections": "🔍 <b>Detections:</b> <code>{}/{}</code>",
        "status_clean": "✅ <b>Status:</b> <code>Clean</code>",
        "status_suspicious": "⚠️ <b>Status:</b> <code>Suspicious</code>",
        "status_malicious": "🚨 <b>Status:</b> <code>Malicious</code>",
        "check_results": "🔎 Check Results",
        "cached_result": "📋 <b>Using cached scan result</b>",
    }

    strings_ru = {
        "no_api_key": "🔑 <b>API ключ не установлен!</b>\n\nПолучите API ключ на <a href='https://www.virustotal.com/gui/my-apikey'>VirusTotal</a> и установите его через <code>.config VirusTotal</code>",
        "no_file": "📎 <b>Ответьте на файл для сканирования!</b>",
        "downloading": "📥 <b>Скачивание файла...</b>",
        "checking_hash": "🔍 <b>Проверка, был ли файл уже отсканирован...</b>",
        "uploading": "📤 <b>Загрузка файла на VirusTotal...</b>",
        "analyzing": "🔬 <b>Анализ файла...</b>\n<i>Это может занять несколько минут</i>",
        "error": "❌ <b>Ошибка:</b> <code>{}</code>",
        "file_too_large": "📦 <b>Файл слишком большой!</b>\nМаксимальный размер: 32 МБ",
        "result_title": "🛡 <b>Результаты сканирования VirusTotal</b>",
        "file_name": "📄 <b>Файл:</b> <code>{}</code>",
        "file_size": "📊 <b>Размер:</b> <code>{}</code>",
        "detections": "🔍 <b>Обнаружения:</b> <code>{}/{}</code>",
        "status_clean": "✅ <b>Статус:</b> <code>Чисто</code>",
        "status_suspicious": "⚠️ <b>Статус:</b> <code>Подозрительно</code>",
        "status_malicious": "🚨 <b>Статус:</b> <code>Вредоносно</code>",
        "check_results": "🔎 Проверить результаты",
        "cached_result": "📋 <b>Использован кэшированный результат</b>",
        "_cmd_doc_vtscan": "Сканировать файл на VirusTotal (ответьте на файл)",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                "",
                lambda: "VirusTotal API Key",
                validator=loader.validators.Hidden(),
            ),
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size to human readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def _calculate_sha256(self, file_data: bytes) -> str:
        """Calculate SHA256 hash of file data"""
        return hashlib.sha256(file_data).hexdigest()

    async def _get_file_report(self, file_hash: str) -> dict:
        """Get file report by hash"""
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        headers = {"x-apikey": self.config["api_key"]}
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def _upload_file(self, file_data: bytes, file_name: str) -> dict:
        """Upload file to VirusTotal"""
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": self.config["api_key"]}
        
        form = aiohttp.FormData()
        form.add_field("file", file_data, filename=file_name)
        
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, data=form) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise Exception(f"Upload failed: {resp.status} - {error_text}")

    async def _get_analysis(self, analysis_id: str) -> dict:
        """Get analysis results"""
        url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
        headers = {"x-apikey": self.config["api_key"]}
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"Failed to get analysis: {resp.status}")

    def _create_progress_bar(self, detections: int, total: int) -> str:
        """Create a visual progress bar for detections"""
        if total == 0:
            return "▓" * 20
        
        percentage = detections / total
        filled = int(percentage * 20)
        empty = 20 - filled
        
        if percentage == 0:
            bar_char = "🟢"
        elif percentage < 0.1:
            bar_char = "🟡"
        elif percentage < 0.3:
            bar_char = "🟠"
        else:
            bar_char = "🔴"
        
        return f"{'▓' * filled}{'░' * empty} {bar_char}"

    def _format_result(self, file_name: str, file_size: int, stats: dict, file_hash: str, cached: bool = False) -> tuple:
        """Format scan results"""
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        harmless = stats.get("harmless", 0)
        total = malicious + suspicious + undetected + harmless
        
        vt_link = f"https://www.virustotal.com/gui/file/{file_hash}"
        
        if malicious > 0:
            status_text = self.strings["status_malicious"]
        elif suspicious > 0:
            status_text = self.strings["status_suspicious"]
        else:
            status_text = self.strings["status_clean"]
        
        detections = malicious + suspicious
        progress_bar = self._create_progress_bar(detections, total)
        
        cached_text = f"\n{self.strings['cached_result']}\n" if cached else "\n"
        
        result_text = (
            f"{self.strings['result_title']}\n"
            f"{'━' * 25}{cached_text}\n"
            f"{self.strings['file_name'].format(file_name)}\n"
            f"{self.strings['file_size'].format(self._format_size(file_size))}\n\n"
            f"{self.strings['detections'].format(detections, total)}\n"
            f"{progress_bar}\n\n"
            f"{status_text}\n\n"
            f"{'━' * 25}"
        )
        
        return result_text, vt_link

    @loader.command(ru_doc="Сканировать файл на VirusTotal (ответьте на файл)")
    async def vtscancmd(self, message):
        """Scan file on VirusTotal (reply to a file)"""
        
        if not self.config["api_key"]:
            await utils.answer(message, self.strings["no_api_key"])
            return
        
        reply = await message.get_reply_message()
        if not reply or not reply.file:
            await utils.answer(message, self.strings["no_file"])
            return
        
        file_size = reply.file.size
        if file_size > 32 * 1024 * 1024:
            await utils.answer(message, self.strings["file_too_large"])
            return
        
        file_name = reply.file.name or "unknown_file"
        
        try:
            await utils.answer(message, self.strings["downloading"])
            file_data = await reply.download_media(bytes)
            
            await utils.answer(message, self.strings["checking_hash"])
            file_hash = self._calculate_sha256(file_data)
            
            existing_report = await self._get_file_report(file_hash)
            
            if existing_report:
                stats = existing_report["data"]["attributes"]["last_analysis_stats"]
                result_text, vt_link = self._format_result(file_name, file_size, stats, file_hash, cached=True)
                
                await self.inline.form(
                    text=result_text,
                    message=message,
                    reply_markup=[
                        [{"text": self.strings["check_results"], "url": vt_link}]
                    ],
                )
                return
            
            await utils.answer(message, self.strings["uploading"])
            
            upload_result = await self._upload_file(file_data, file_name)
            analysis_id = upload_result["data"]["id"]
            
            await utils.answer(message, self.strings["analyzing"])
            
            max_attempts = 60
            analysis = None
            for _ in range(max_attempts):
                await asyncio.sleep(5)
                try:
                    analysis = await self._get_analysis(analysis_id)
                    status = analysis["data"]["attributes"]["status"]
                    
                    if status == "completed":
                        break
                except Exception as e:
                    logger.warning(f"Error getting analysis: {e}")
                    continue
            else:
                await utils.answer(message, self.strings["error"].format("Analysis timeout"))
                return
            
            stats = analysis["data"]["attributes"]["stats"]
            result_text, vt_link = self._format_result(file_name, file_size, stats, file_hash, cached=False)
            
            await self.inline.form(
                text=result_text,
                message=message,
                reply_markup=[
                    [{"text": self.strings["check_results"], "url": vt_link}]
                ],
            )
            
        except Exception as e:
            logger.exception("VirusTotal scan error")
            await utils.answer(message, self.strings["error"].format(str(e)))