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

from .. import loader, utils
import aiohttp
from datetime import datetime

@loader.tds
class GitMod(loader.Module):
    """
    Module for fetching GitHub repository information.
    Shows stars, forks, watchers, language, and allows viewing commits/README/License via inline buttons.
    """
    strings = {"name": "GitMod"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "language",
                "ru",
                "Language (en, ru, uk)",
                validator=loader.validators.Choice(["en", "ru", "uk"]),
            ),
            loader.ConfigValue(
                "api_key",
                None,
                "GitHub API Key (Personal Access Token). Increases rate limits.",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
        )

    LOCALES = {
        "en": {
            "repo_not_found": "❌ <b>Repository not found.</b> Check the username/repo name.",
            "api_error": "❌ <b>GitHub API Error.</b> Try again later or check API Key.",
            "info_header": "🐙 <b>GitHub Info:</b> <code>{}</code>\n",
            "stars": "⭐ <b>Stars:</b>",
            "forks": "🍴 <b>Forks:</b>",
            "watchers": "👀 <b>Watchers:</b>",
            "lang": "💻 <b>Language:</b>",
            "last_commit": "📅 <b>Last Commit:</b>",
            "btn_link": "🔗 Link",
            "btn_commits": "📝 Commits",
            "btn_readme": "📄 README",
            "btn_license": "⚖️ License",
            "btn_close": "❌ Close",
            "btn_back": "🔙 Back",
            "fetching": "🔄 <b>Fetching info...</b>",
            "commits_header": "📝 <b>Last 5 Commits for</b> <code>{}</code>:\n\n",
            "readme_header": "📄 <b>README Preview:</b> <code>{}</code>\n",
            "read_full": "🔗 <a href='{}'>Read full raw file</a>",
            "license_header": "⚖️ <b>License:</b> <code>{}</code>\n",
            "license_not_found": "License not found.",
            "download_fail": "Failed to download content.",
            "usage": "❌ <b>Usage:</b> <code>.git user/repo</code>"
        },
        "ru": {
            "repo_not_found": "❌ <b>Репозиторий не найден.</b> Проверьте имя пользователя/репозитория.",
            "api_error": "❌ <b>Ошибка GitHub API.</b> Попробуйте позже или проверьте API ключ.",
            "info_header": "🐙 <b>GitHub Инфо:</b> <code>{}</code>\n",
            "stars": "⭐ <b>Звезды:</b>",
            "forks": "🍴 <b>Форки:</b>",
            "watchers": "👀 <b>Наблюдатели:</b>",
            "lang": "💻 <b>Язык:</b>",
            "last_commit": "📅 <b>Последний коммит:</b>",
            "btn_link": "🔗 Ссылка",
            "btn_commits": "📝 Коммиты",
            "btn_readme": "📄 README",
            "btn_license": "⚖️ Лицензия",
            "btn_close": "❌ Закрыть",
            "btn_back": "🔙 Назад",
            "fetching": "🔄 <b>Получение информации...</b>",
            "commits_header": "📝 <b>Последние 5 коммитов для</b> <code>{}</code>:\n\n",
            "readme_header": "📄 <b>Превью README:</b> <code>{}</code>\n",
            "read_full": "🔗 <a href='{}'>Читать полный файл</a>",
            "license_header": "⚖️ <b>Лицензия:</b> <code>{}</code>\n",
            "license_not_found": "Лицензия не найдена.",
            "download_fail": "Не удалось загрузить содержимое.",
            "usage": "❌ <b>Использование:</b> <code>.git user/repo</code>"
        },
        "uk": {
            "repo_not_found": "❌ <b>Репозиторій не знайдено.</b> Перевірте ім'я користувача/репозиторія.",
            "api_error": "❌ <b>Помилка GitHub API.</b> Спробуйте пізніше або перевірте API ключ.",
            "info_header": "🐙 <b>GitHub Інфо:</b> <code>{}</code>\n",
            "stars": "⭐ <b>Зірки:</b>",
            "forks": "🍴 <b>Форки:</b>",
            "watchers": "👀 <b>Спостерігачі:</b>",
            "lang": "💻 <b>Мова:</b>",
            "last_commit": "📅 <b>Останній коміт:</b>",
            "btn_link": "🔗 Посилання",
            "btn_commits": "📝 Коміти",
            "btn_readme": "📄 README",
            "btn_license": "⚖️ Ліцензія",
            "btn_close": "❌ Закрити",
            "btn_back": "🔙 Назад",
            "fetching": "🔄 <b>Отримання інформації...</b>",
            "commits_header": "📝 <b>Останні 5 комітів для</b> <code>{}</code>:\n\n",
            "readme_header": "📄 <b>Прев'ю README:</b> <code>{}</code>\n",
            "read_full": "🔗 <a href='{}'>Читати повний файл</a>",
            "license_header": "⚖️ <b>Ліцензія:</b> <code>{}</code>\n",
            "license_not_found": "Ліцензію не знайдено.",
            "download_fail": "Не вдалося завантажити вміст.",
            "usage": "❌ <b>Використання:</b> <code>.git user/repo</code>"
        }
    }

    async def client_ready(self, client, db):
        self.client = client

    def _get_str(self, key):
        lang = self.config["language"]
        return self.LOCALES.get(lang, self.LOCALES["en"]).get(key, key)

    async def _fetch_data(self, url):
        headers = {
            "User-Agent": "Hikka-Userbot",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        if self.config["api_key"]:
            headers["Authorization"] = f"Bearer {self.config['api_key']}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        return False
                    return await resp.json()
        except Exception:
            return False

    async def _generate_card(self, repo_name):
        data = await self._fetch_data(f"https://api.github.com/repos/{repo_name}")
        
        if data is None:
            return self._get_str("repo_not_found"), None
        if data is False:
            return self._get_str("api_error"), None

        # Extract Data
        name = data.get("full_name", "Unknown")
        desc = data.get("description")
        desc = f"<i>{desc}</i>\n\n" if desc else "\n"
        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        watchers = data.get("subscribers_count", 0)
        lang = data.get("language") or "None"
        
        # Date Formatting
        pushed = data.get("pushed_at", "")
        if pushed:
            try:
                dt = datetime.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ")
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date_str = pushed
        else:
            date_str = "Unknown"

        text = (
            f"{self._get_str('info_header').format(name)}"
            f"{desc}"
            f"{self._get_str('stars')} {stars} | {self._get_str('forks')} {forks}\n"
            f"{self._get_str('watchers')} {watchers}\n"
            f"{self._get_str('lang')} {lang}\n"
            f"{self._get_str('last_commit')} {date_str}"
        )

        buttons = [
            [{"text": self._get_str("btn_link"), "url": data.get("html_url", "https://github.com")}],
            [
                {"text": self._get_str("btn_commits"), "callback": self._commits_cb, "args": (repo_name,)},
                {"text": self._get_str("btn_readme"), "callback": self._readme_cb, "args": (repo_name,)},
                {"text": self._get_str("btn_license"), "callback": self._license_cb, "args": (repo_name,)}
            ],
            [{"text": self._get_str("btn_close"), "action": "close"}]
        ]

        return text, buttons

    @loader.command(
        ru_doc="<user/repo> - Получить информацию о репозитории",
        en_doc="<user/repo> - Get repository information"
    )
    async def gitcmd(self, message):
        """<user/repo> - Get GitHub repository info"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self._get_str("usage"))

        # Clean arguments (remove full URL if pasted)
        args = args.replace("https://github.com/", "").strip("/")
        
        # Handle loading state
        if message.out:
            await utils.answer(message, self._get_str("fetching"))
        
        text, buttons = await self._generate_card(args)
        
        if not buttons: # Error case
            return await utils.answer(message, text)

        await self.inline.form(
            text=text,
            message=message,
            reply_markup=buttons
        )

    async def _back_cb(self, call, repo_name):
        """Callback to return to main card"""
        text, buttons = await self._generate_card(repo_name)
        await call.edit(text=text, reply_markup=buttons)

    async def _commits_cb(self, call, repo_name):
        """Callback to show commits"""
        data = await self._fetch_data(f"https://api.github.com/repos/{repo_name}/commits?per_page=5")
        
        if not data:
            return await call.answer(self._get_str("api_error"), show_alert=True)
        
        text = self._get_str("commits_header").format(repo_name)
        
        for c in data:
            sha = c.get('sha', '.......')[:7]
            msg = c.get('commit', {}).get('message', 'No message').split('\n')[0]
            author = c.get('commit', {}).get('author', {}).get('name', 'Unknown')
            # Escape HTML in message just in case
            msg = utils.escape_html(msg)
            text += f"• <code>{sha}</code>: {msg} (<b>{author}</b>)\n"

        buttons = [[{"text": self._get_str("btn_back"), "callback": self._back_cb, "args": (repo_name,)}]]
        await call.edit(text=text, reply_markup=buttons)

    async def _readme_cb(self, call, repo_name):
        """Callback to show README preview"""
        data = await self._fetch_data(f"https://api.github.com/repos/{repo_name}/readme")
        
        if not data or "download_url" not in data:
            return await call.answer("README not found.", show_alert=True)

        download_url = data["download_url"]
        
        # Fetch raw content
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return await call.answer(self._get_str("download_fail"), show_alert=True)
                    content = await resp.text()
        except Exception:
             return await call.answer(self._get_str("download_fail"), show_alert=True)

        # Create preview (max 1000 chars)
        preview = content[:1000]
        if len(content) > 1000:
            preview += "..."
        
        # Escape HTML tags to prevent broken formatting
        preview = utils.escape_html(preview)

        text = (
            f"{self._get_str('readme_header').format(repo_name)}"
            f"_________________\n"
            f"{preview}\n"
            f"_________________\n"
            f"{self._get_str('read_full').format(download_url)}"
        )

        buttons = [[{"text": self._get_str("btn_back"), "callback": self._back_cb, "args": (repo_name,)}]]
        await call.edit(text=text, reply_markup=buttons)

    async def _license_cb(self, call, repo_name):
        """Callback to show License"""
        data = await self._fetch_data(f"https://api.github.com/repos/{repo_name}/license")
        
        if not data or "download_url" not in data:
            return await call.answer(self._get_str("license_not_found"), show_alert=True)

        download_url = data["download_url"]
        
        # Fetch raw content
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return await call.answer(self._get_str("download_fail"), show_alert=True)
                    content = await resp.text()
        except Exception:
             return await call.answer(self._get_str("download_fail"), show_alert=True)

        # Create preview (max 1000 chars)
        preview = content[:1000]
        if len(content) > 1000:
            preview += "..."
        
        # Escape HTML tags
        preview = utils.escape_html(preview)

        text = (
            f"{self._get_str('license_header').format(repo_name)}"
            f"_________________\n"
            f"{preview}\n"
            f"_________________\n"
            f"{self._get_str('read_full').format(download_url)}"
        )

        buttons = [[{"text": self._get_str("btn_back"), "callback": self._back_cb, "args": (repo_name,)}]]
        await call.edit(text=text, reply_markup=buttons)
