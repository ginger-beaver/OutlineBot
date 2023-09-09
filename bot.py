import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject
from dotenv import load_dotenv
from outline_vpn_api import OutlineVPN

logging.basicConfig(level=logging.INFO)
load_dotenv()


bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(f"Привет, {message.from_user.username}! \nЭто бот для управления VPN сервером."
                         f" Воспользуйтесь кнопкой menu ниже для просмотра cписка команд.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message, client: OutlineVPN):
    formatted_keys = [(key.name, 0 if key.used_bytes is None else key.used_bytes, key.data_limit)
                      for key in await client.get_keys()]
    formatted_keys.sort(key=lambda k: k[1], reverse=True)
    await message.answer(';\n'.join(
        f"{key[0]}: {round(key[1] * 1e-9, 2)} ГБ / {key[2]}"
        for key in formatted_keys
    ))


@dp.message(Command("create"))
async def cmd_create(message: types.Message, command: CommandObject, client: OutlineVPN):
    new_key = await client.create_key(command.args)
    await message.answer(f"Ключ ID: {new_key.key_id}, Name: '{new_key.name}' создан!")
    await message.answer(f"<code>{new_key.access_url}</code>", parse_mode="HTML")


@dp.message(Command("del"))
async def cmd_del(message: types.Message, command: CommandObject, client: OutlineVPN):
    try:
        parsed_id = int(command.args)
        text = "удален!" if await client.delete_key(parsed_id) else "не существует!"
        await message.answer(f"Ключ ID: {parsed_id} {text}")
    except (ValueError, TypeError):
        await message.answer(f"Неправильный формат аргумента!")


@dp.message(Command("get_keys"))
async def cmd_get_keys(message: types.Message, client: OutlineVPN):
    formatted_keys = (f"ID: {key.key_id}, Name: {key.name}\n<code>{key.access_url}</code>"
                      for key in await client.get_keys())
    await message.answer(';\n'.join(formatted_keys), parse_mode="HTML")


class OutlineSessionMiddleware(BaseMiddleware):
    def __init__(self, session):
        self.session = session

    async def __call__(self, handler, event, data):
        data["client"] = self.session
        return await handler(event, data)


async def main():
    client = OutlineVPN(api_url=os.getenv("OUTLINE_TOKEN"), fingerprint=os.getenv("FINGERPRINT"))
    dp.message.middleware(OutlineSessionMiddleware(client))
    dp.message.filter(F.from_user.id == int(os.getenv("ADMIN_ID")))
    dp.shutdown.register(client.close)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")