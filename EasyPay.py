# meta developer: @TypeFrag
from .. import loader, utils
import requests
import logging

logger = logging.getLogger(__name__)

@loader.tds
class EasyPayMod(loader.Module):
    """
    Модуль для быстрой генерации счетов через Банковскую карту, Телефон, CryptoBot и Tonkeeper.
    Автоматически рассчитывает курсы валют.
    """

    strings = {"name": "EasyPay"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "bank_card",
                "",
                "Ваш номер банковской карты для отображения.",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "bank_phone",
                "",
                "Ваш номер телефона, привязанный к банку.",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "cryptobot_token",
                "",
                "API Токен от @CryptoBot (создайте приложение в боте).",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "ton_wallet",
                "",
                "Ваш адрес кошелька TON для Tonkeeper.",
                validator=loader.validators.String(),
            ),
        )

    async def client_ready(self, client, db):
        self.client = client

    def _get_rates(self, amount_rub):
        try:
            # Используем бесплатный API для курсов
            r = requests.get(
                "https://min-api.cryptocompare.com/data/price?fsym=RUB&tsyms=USD,TON,BTC"
            ).json()
            
            usd_rate = r.get("USD", 0)
            ton_rate = r.get("TON", 0)
            btc_rate = r.get("BTC", 0)

            return {
                "USD": round(amount_rub * usd_rate, 2),
                "TON": round(amount_rub * ton_rate, 4),
                "BTC": round(amount_rub * btc_rate, 8),
            }
        except Exception as e:
            logger.error(f"Rate fetch error: {e}")
            return None

    def _create_cryptobot_invoice(self, amount_usd):
        token = self.config["cryptobot_token"]
        if not token:
            return None
        
        try:
            headers = {"Crypto-Pay-API-Token": token}
            data = {
                "asset": "USDT",
                "amount": str(amount_usd),
                "description": "Payment via EasyPay",
                "allow_comments": False,
                "allow_anonymous": True,
            }
            r = requests.post(
                "https://pay.crypt.bot/api/createInvoice", json=data, headers=headers
            )
            res = r.json()
            if res.get("ok"):
                return res["result"]["pay_url"]
            else:
                logger.error(f"CryptoBot Error: {res}")
                return None
        except Exception as e:
            logger.error(f"CryptoBot Request Error: {e}")
            return None

    @loader.command(
        ru_doc="<сумма> - Создать счет на оплату. Кнопки доступны собеседнику (используйте реплай)."
    )
    async def paycmd(self, message):
        """<сумма> - Создать счет на оплату. Кнопки доступны собеседнику."""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "❌ <b>Пожалуйста, укажите сумму в рублях.</b>")
            return

        try:
            amount = float(args.replace(",", "."))
        except ValueError:
            await utils.answer(message, "❌ <b>Сумма должна быть числом.</b>")
            return

        rates = self._get_rates(amount)
        if not rates:
            await utils.answer(message, "❌ <b>Не удалось получить курсы валют.</b>")
            return

        # Define button callbacks
        async def card_handler(call):
            card = self.config["bank_card"] or "Не установлено"
            await call.answer(f"💳 Номер карты:\n{card}", show_alert=True)

        async def phone_handler(call):
            phone = self.config["bank_phone"] or "Не установлено"
            await call.answer(f"📱 Номер телефона:\n{phone}", show_alert=True)

        async def cryptobot_handler(call):
            if not self.config["cryptobot_token"]:
                await call.answer("❌ Токен CryptoBot не настроен.", show_alert=True)
                return
            
            await call.answer("⏳ Генерация счета...", show_alert=False)
            link = self._create_cryptobot_invoice(rates["USD"])
            
            if link:
                await call.edit(
                    text=f"<b>🤖 Счет CryptoBot</b>\n\n💵 Сумма: <code>{rates['USD']} USDT</code>",
                    reply_markup=[[{"text": "🔗 Оплатить через CryptoBot", "url": link}], [{"text": "🔙 Назад", "callback": back_handler}]]
                )
            else:
                await call.answer("❌ Не удалось создать счет.", show_alert=True)

        async def ton_handler(call):
            wallet = self.config["ton_wallet"]
            if not wallet:
                await call.answer("❌ TON кошелек не настроен.", show_alert=True)
                return

            ton_amount = rates["TON"]
            # 1 TON = 1,000,000,000 nanotons
            nanotons = int(ton_amount * 1_000_000_000)
            
            link = f"https://app.tonkeeper.com/transfer/{wallet}?amount={nanotons}&text=Payment"
            
            text = (
                f"<b>💎 Оплата через Tonkeeper</b>\n\n"
                f"👛 <b>Кошелек:</b> <code>{wallet}</code>\n"
                f"💎 <b>TON:</b> <code>{ton_amount}</code>\n"
                f"💵 <b>USD:</b> <code>{rates['USD']}</code>\n"
                f"🪙 <b>BTC:</b> <code>{rates['BTC']}</code>"
            )
            
            await call.edit(
                text=text,
                reply_markup=[
                    [{"text": "💸 Оплатить через Tonkeeper", "url": link}],
                    [{"text": "🔙 Назад", "callback": back_handler}]
                ]
            )

        async def back_handler(call):
            await call.edit(
                text=main_text,
                reply_markup=main_markup
            )

        # Main Menu Construction
        main_text = (
            f"<b>💸 Счет на оплату</b>\n\n"
            f"🇷🇺 <b>Сумма:</b> <code>{amount} RUB</code>\n"
            f"🇺🇸 <b>~USD:</b> <code>{rates['USD']} $</code>\n\n"
            f"👇 <b>Выберите способ оплаты:</b>"
        )
        
        main_markup = [
            [
                {"text": "💳 Карта", "callback": card_handler},
                {"text": "📱 Телефон", "callback": phone_handler},
            ],
            [
                {"text": f"🤖 CryptoBot (~{rates['USD']} $)", "callback": cryptobot_handler},
            ],
            [
                {"text": f"💎 Tonkeeper (~{rates['TON']} TON)", "callback": ton_handler},
            ]
        ]

        # Determine who can access the buttons
        allowed_users = [message.sender_id]
        reply = await message.get_reply_message()
        if reply:
            allowed_users.append(reply.sender_id)

        await self.inline.form(
            text=main_text,
            message=message,
            reply_markup=main_markup,
            always_allow=allowed_users
        )