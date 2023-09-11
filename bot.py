import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject
from dotenv import load_dotenv
from outline_vpn_api import OutlineVPN, OutlineKey

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
    keys = await client.get_keys()
    keys.sort(key=lambda k: k.used_bytes, reverse=True)
    await message.answer(';\n'.join(
        f"ID {key.key_id}, {key.name}: "
        f"{round(key.used_bytes * 1e-9, 2)} ГБ / {round(key.data_limit * 1e-9, 2)}"
        for key in keys
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

@dp.message(Command("get_key"))
async def cmd_get_key(message: types.Message, command: CommandObject, client: OutlineVPN):
    try:
        parsed_id = int(command.args)
        key = await client.get_key(parsed_id)
        if key:
            key_stats = f"{round(key.used_bytes * 1e-9, 2)} / {round(key.data_limit * 1e-9, 2)} ГБ"
            await message.answer(f"ID: {key.key_id}, Name: {key.name}, {key_stats}"
                                 f"\n<code>{key.access_url}</code>", parse_mode="HTML")
        else:
            await message.answer(f"Ключ ID: {parsed_id} не существует!")
    except (ValueError, TypeError):
        await message.answer(f"Неправильный формат аргумента!")

@dp.message(Command("get_default_limit"))
async def cmd_get_default(message: types.Message, client: OutlineVPN):
    data = await client.get_default_data_limit()
    text = f"{data * 1e-9} ГБ" if data else "не установлен!"
    await message.answer(f"Общий лимит {text}")


# @dp.message(Command("set_default_limit"))
# async def cmd_set_default_limit(message: types.Message, command: CommandObject, client: OutlineVPN):
#     try:
#         parsed_bytes = int(command.args)
#         if await client.set_default_data_limit(int(parsed_bytes * 1e+9)):
#             await message.answer(f"Лимит в {parsed_bytes} ГБ установлен!")
#         else:
#             await message.answer("Не удалось установить лимит!")
#     except (ValueError, TypeError):
#         await message.answer(f"Неправильный формат аргумента!")
#
# @dp.message(Command("del_default_limit"))
# async def cmd_del_default_limit(message: types.Message, client: OutlineVPN):
#     if await client.delete_default_data_limit():
#         await message.answer("Лимит удален!")
#     else:
#         await message.answer("Не удалось удалить лимит!")


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
